import os
import logging
import yt_dlp
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(str, int, int, object)

class DownloadWorker(QRunnable):
    def __init__(self, url, ydl_opts):
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts
        self.signals = WorkerSignals()
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                self.logger.info(f"İndirme başlatılıyor: {self.url}")
                ydl.download([self.url])
            self.signals.finished.emit()
            self.logger.info(f"İndirme tamamlandı: {self.url}")
        except Exception as e:
            self.logger.error(f"İndirme hatası: {str(e)}, URL: {self.url}")
            self.signals.error.emit(str(e))

class YouTubeDownloader(QObject):
    progress_signal = pyqtSignal(str, int, int, object)
    download_progress_signal = pyqtSignal(str, float, float)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.ydl_opts = {
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        }

        self.thread_pool = QThreadPool()
        self.logger.info(f"Multithreading with maximum {self.thread_pool.maxThreadCount()} threads")

    def get_video_info(self, url):
        self.logger.info(f"Fetching video info for URL: {url}")
        worker = VideoInfoWorker(url, self.ydl_opts, self.get_available_formats)
        worker.signals.progress.connect(self.progress_signal.emit)
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.error.connect(self.on_worker_error)
        self.thread_pool.start(worker)
        return worker

    def get_playlist_info(self, url):
        self.logger.info(f"Fetching playlist info for URL: {url}")
        worker = PlaylistInfoWorker(url, self.ydl_opts, self.get_available_formats)
        worker.signals.progress.connect(self.progress_signal.emit)
        worker.signals.finished.connect(self.on_worker_finished)
        worker.signals.error.connect(self.on_worker_error)
        self.thread_pool.start(worker)
        return worker

    def on_worker_finished(self):
        self.logger.info("Worker finished successfully")
        self.progress_signal.emit("İşlem tamamlandı", 100, 100, None)

    def on_worker_error(self, error):
        self.logger.error(f"Worker encountered an error: {error}")
        self.progress_signal.emit(f"Hata oluştu: {error}", 0, 100, None)

    def get_available_formats(self, info):
        video_formats = []
        audio_formats = []
        seen_resolutions = set()

        for f in info.get('formats', []):
            if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                height = f.get('height', 0)
                format_id = f.get('format_id', 'unknown')
                vbr = f.get('vbr', 0)
                format_note = f"{height}p"

                if format_note not in seen_resolutions:
                    video_formats.append((format_note, format_id, vbr))
                    seen_resolutions.add(format_note)
                else:
                    for i, (res, fid, old_vbr) in enumerate(video_formats):
                        if res == format_note and vbr > old_vbr:
                            video_formats[i] = (format_note, format_id, vbr)
                            break

            if f.get('acodec', 'none') != 'none' and f.get('vcodec') == 'none':
                abr = f.get('abr', 0)
                format_id = f.get('format_id', 'unknown')
                audio_formats.append((f"{abr}kbps", format_id))

        video_formats = sorted(video_formats, key=lambda x: int(x[0].split('p')[0]), reverse=True)
        video_formats = [(f"{res} ({vbr:.1f}Mbps)", fid) for res, fid, vbr in video_formats]

        audio_formats = sorted(set(audio_formats), key=lambda x: float(x[0].split('kbps')[0]), reverse=True)

        video_formats.insert(0, ("En İyi Kalite", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"))

        return video_formats, audio_formats

    def download_video(self, url, format_id, output_path):
        self.logger.info(f"Starting download: URL={url}, format_id={format_id}, output_path={output_path}")

        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'progress_hooks': [self.progress_hook],
        }

        if 'audio' in format_id.lower():
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]

        worker = DownloadWorker(url, ydl_opts)
        worker.signals.progress.connect(self.download_progress_signal.emit)
        worker.signals.finished.connect(self.on_download_finished)
        worker.signals.error.connect(self.on_download_error)
        self.thread_pool.start(worker)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            filename = os.path.basename(d.get('filename', ''))
            self.download_progress_signal.emit(filename, downloaded, total)

    def on_download_finished(self):
        self.logger.info("Download finished")
        self.progress_signal.emit("İndirme tamamlandı", 100, 100, None)

    def on_download_error(self, error):
        self.logger.error(f"Download error: {error}")
        self.progress_signal.emit(f"İndirme hatası: {error}", 0, 100, None)

class VideoInfoWorker(QRunnable):
    def __init__(self, url, ydl_opts, get_available_formats):
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts
        self.get_available_formats = get_available_formats
        self.signals = WorkerSignals()
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                self.signals.progress.emit("Video bilgileri alınıyor...", 0, 100, None)
                info = ydl.extract_info(self.url, download=False)
                if info is None:
                    raise ValueError("Video bilgisi alınamadı.")
                self.process_info(info)
        except Exception as e:
            self.logger.error(f"Video bilgisi alınırken hata oluştu: {str(e)}")
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

    def process_info(self, info):
        try:
            self.logger.debug("Video bilgileri işleniyor...")
            video_formats, audio_formats = self.get_available_formats(info)
            video_info = {
                'title': info.get('title', 'Başlık Alınamadı'),
                'duration_string': info.get('duration_string', '00:00'),
                'video_formats': video_formats,
                'audio_formats': audio_formats,
                'webpage_url': info.get('webpage_url'),
                'formats': info.get('formats', []),
            }
            self.logger.debug(f"İşlenmiş video bilgileri: {video_info}")
            self.signals.progress.emit("Video bilgileri alındı.", 100, 100, video_info)
        except Exception as e:
            self.logger.error(f"Video bilgisi işlenirken hata: {str(e)}")
            self.signals.error.emit(f"Video bilgisi işlenirken hata: {str(e)}")

    @staticmethod
    def format_duration(seconds):
        if seconds is None:
            return "00:00"
        try:
            seconds = int(float(seconds))
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes:02d}:{seconds:02d}"
        except ValueError:
            return "00:00"

class PlaylistInfoWorker(QRunnable):
    def __init__(self, url, ydl_opts, get_available_formats):
        super().__init__()
        self.url = url
        self.ydl_opts = ydl_opts
        self.get_available_formats = get_available_formats
        self.signals = WorkerSignals()
        self.logger = logging.getLogger(__name__)

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                self.signals.progress.emit("Playlist bilgileri alınıyor...", 0, 100, None)
                playlist_info = ydl.extract_info(self.url, download=False)
                if playlist_info is None:
                    raise ValueError("Playlist bilgisi alınamadı.")
                self.process_info(playlist_info)
        except Exception as e:
            self.logger.error(f"Playlist bilgisi alınırken hata oluştu: {str(e)}")
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

    def process_info(self, playlist_info):
        if 'entries' not in playlist_info:
            self.signals.error.emit("Bu bir playlist URL'si değil")
            return

        total_videos = len(playlist_info['entries'])
        self.logger.info(f"Playlist: {playlist_info.get('title', 'Başlık Alınamadı')} - Toplam Video: {total_videos}")
        self.signals.progress.emit(
            f"Playlist: {playlist_info.get('title', 'Başlık Alınamadı')} - Toplam Video: {total_videos}",
            10, 100, None
        )

        playlist_videos = []
        for i, entry in enumerate(playlist_info['entries']):
            if entry is not None:
                try:
                    video_formats, audio_format = self.get_available_formats(entry)
                    video_info = {
                        'title': entry.get('title', 'Video Başlığı Alınamadı'),
                        'duration': self.format_duration(entry.get('duration', 0)),
                        'video_formats': video_formats,
                        'audio_format': audio_format,
                        'webpage_url': entry.get('webpage_url'),
                    }
                    playlist_videos.append(video_info)
                    progress = 10 + int((i + 1) / total_videos * 90)
                    self.signals.progress.emit(f"Video bilgisi alınıyor ({i + 1}/{total_videos})", progress, 100,
                                               video_info)
                    self.logger.debug(f"Video bilgisi alındı: {video_info['title']}")
                except Exception as e:
                    self.logger.error(f"Video bilgisi alınamadı: {i + 1}/{total_videos}, Hata: {str(e)}")
                    self.signals.progress.emit(f"Video bilgisi alınamadı: {i + 1}/{total_videos}", progress, 100, None)

        self.signals.progress.emit("Playlist bilgileri alındı.", 100, 100, {'playlist_videos': playlist_videos})
        self.logger.info(f"Playlist işleme tamamlandı. Toplam video sayısı: {len(playlist_videos)}")

    @staticmethod
    def format_duration(seconds):
        if seconds is None:
            return "00:00"
        try:
            seconds = int(float(seconds))
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                return f"{minutes:02d}:{seconds:02d}"
        except ValueError:
            return "00:00"