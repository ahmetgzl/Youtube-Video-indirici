import os
import time
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                             QComboBox, QLabel, QProgressBar, QListWidget, QApplication,
                             QGroupBox, QMessageBox, QTableWidget, QTableWidgetItem,
                             QAbstractItemView, QHeaderView, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QObject, QThreadPool, QRunnable
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QNetworkAccessManager
from downloader import YouTubeDownloader

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, 'resources', 'icons')


class YouTubeDownloaderGUI(QWidget):
    def __init__(self):
        super().__init__()
        # Temel logger ayarları
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        # YouTubeDownloader sınıfının örneğini oluştur
        self.downloader = YouTubeDownloader()
        self.downloader.progress_signal.connect(self.update_progress)
        self.downloader.download_progress_signal.connect(self.update_download_progress)

        # Ağ yöneticisi oluştur (gelecekteki kullanım için)
        self.network_manager = QNetworkAccessManager()

        # Playlist yükleme iptal bayrağı
        self.cancel_playlist_loading = False

        # Arayüzü başlat
        self.initUI()

        # İlerleme çubuğunu ayarla
        self.progress_bar.setRange(0, 100)

        # Geçici veri saklama listesi
        self.temp_video_info = []

        # Şu anki worker'ı saklamak için değişken
        self.current_worker = None

        # Thread havuzu oluştur
        self.thread_pool = QThreadPool()
        self.logger.debug(f"Multithreading with maximum {self.thread_pool.maxThreadCount()} threads")

    def initUI(self):
        self.setWindowTitle('YouTube Video İndirici')
        self.setMinimumSize(800, 600)
        self.setWindowIcon(QIcon(os.path.join(ICON_DIR, "app_icon.png")))

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        # URL giriş bölümü
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube video veya playlist URL'sini girin")
        self.fetch_btn = QPushButton(QIcon(os.path.join(ICON_DIR, "info_icon.png")), "Bilgi Al")
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_btn)
        main_layout.addLayout(url_layout)

        # Video/Playlist bilgisi ve indirme seçenekleri bölümü
        info_options_layout = QHBoxLayout()

        # Video/Playlist bilgisi (alanın %70'i)
        info_group = QGroupBox("Video/Playlist Bilgisi")
        info_layout = QVBoxLayout(info_group)

        self.video_table = QTableWidget()
        self.video_table.setColumnCount(4)
        self.video_table.setHorizontalHeaderLabels(["Seç", "Başlık", "Süre", "Durum"])
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        info_layout.addWidget(self.video_table)

        self.video_count_label = QLabel("Toplam video sayısı: 0")
        info_layout.addWidget(self.video_count_label)

        info_options_layout.addWidget(info_group, 65)

        # İndirme seçenekleri (alanın %30'u)
        options_group = QGroupBox("İndirme Seçenekleri")
        options_layout = QVBoxLayout(options_group)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Video (MP4)", "Ses (MP3)"])
        format_layout.addWidget(self.format_combo)
        options_layout.addLayout(format_layout)

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Kalite:"))
        self.quality_combo = QComboBox()
        quality_layout.addWidget(self.quality_combo)
        options_layout.addLayout(quality_layout)

        file_path_layout = QHBoxLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("İndirme konumu")
        self.file_path_btn = QPushButton(QIcon(os.path.join(ICON_DIR, "folder_icon.png")), "")
        file_path_layout.addWidget(self.file_path_input)
        file_path_layout.addWidget(self.file_path_btn)
        options_layout.addLayout(file_path_layout)

        self.download_btn = QPushButton(QIcon(os.path.join(ICON_DIR, "download_icon.png")), "İndir")
        self.download_btn.setObjectName("download_btn")
        options_layout.addWidget(self.download_btn)

        speed_time_layout = QVBoxLayout()
        self.speed_label = QLabel("İndirme Hızı: -")
        self.time_label = QLabel("Tahmini Süre: -")
        speed_time_layout.addWidget(self.speed_label)
        speed_time_layout.addWidget(self.time_label)
        options_layout.addLayout(speed_time_layout)

        info_options_layout.addWidget(options_group, 35)

        main_layout.addLayout(info_options_layout)

        # İlerleme bölümü
        progress_group = QGroupBox("İndirme Durumu")
        progress_layout = QVBoxLayout(progress_group)
        self.status_label = QLabel("Hazır")
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)

        # İndirme kontrol butonları
        control_layout = QHBoxLayout()
        self.pause_btn = QPushButton(QIcon(os.path.join(ICON_DIR, "pause_icon.png")), "Duraklat")
        self.pause_btn.setObjectName("pause_btn")
        self.resume_btn = QPushButton(QIcon(os.path.join(ICON_DIR, "resume_icon.png")), "Devam Et")
        self.resume_btn.setObjectName("resume_btn")
        self.cancel_btn = QPushButton(QIcon(os.path.join(ICON_DIR, "cancel_icon.png")), "İptal Et")
        self.cancel_btn.setObjectName("cancel_btn")
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.resume_btn)
        control_layout.addWidget(self.cancel_btn)
        progress_layout.addLayout(control_layout)

        main_layout.addWidget(progress_group)

        # İndirme geçmişi bölümü
        history_group = QGroupBox("İndirme Geçmişi")
        history_layout = QVBoxLayout(history_group)
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        main_layout.addWidget(history_group)

        # Telif hakkı metni
        copyright_label = QLabel("YouTube Video İndirici - 2024 - bigfiggings")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setObjectName("copyright_label")
        main_layout.addWidget(copyright_label)

        self.setLayout(main_layout)
        self.setup_connections()
        self.progress_bar.setVisible(True)

    def setup_connections(self):
        self.fetch_btn.clicked.connect(self.fetch_info)
        self.file_path_btn.clicked.connect(self.select_directory)
        self.format_combo.currentIndexChanged.connect(self.update_quality_options)
        self.video_table.itemChanged.connect(self.update_video_selection)
        self.download_btn.clicked.connect(self.start_download)
        # Yeni bağlantılar eklenebilir (örneğin, duraklat, devam et, iptal et butonları için)

    def adjust_table_columns(self):
        self.video_table.setColumnWidth(0, 30)  # Checkbox sütunu
        self.video_table.setColumnWidth(2, 70)  # Süre sütunu
        self.video_table.setColumnWidth(3, 100)  # Durum sütunu
        remaining_width = self.video_table.width() - 200  # 30 + 70 + 100
        self.video_table.setColumnWidth(1, remaining_width)  # Başlık sütunu
        self.video_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.video_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.video_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.video_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adjust_table_columns()

    def fetch_info(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Hata", "Lütfen bir URL girin.")
            return

        if not (url.startswith('https://www.youtube.com/') or url.startswith('https://youtu.be/')):
            QMessageBox.warning(self, "Hata",
                                "Geçersiz YouTube URL'si. Lütfen geçerli bir YouTube video veya playlist URL'si girin.")
            return

        self.progress_bar.setValue(0)
        self.status_label.setText("Bilgiler alınıyor...")
        self.video_table.setRowCount(0)
        self.temp_video_info.clear()

        if 'list=' in url:
            worker = self.downloader.get_playlist_info(url)
        else:
            worker = self.downloader.get_video_info(url)

        self.current_worker = worker
        worker.signals.progress.connect(self.update_progress)
        worker.signals.error.connect(self.show_error)
        worker.signals.finished.connect(self.on_worker_finish)

    def show_error(self, error):
        QMessageBox.critical(self, "Hata", str(error))

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "İndirme Konumunu Seç")
        if directory:
            self.file_path_input.setText(directory)

    def update_progress(self, status, current, total, video_info):
        self.status_label.setText(status)
        self.progress_bar.setValue(int((current / total) * 100))

        if video_info and isinstance(video_info, dict):
            self.process_video_info(video_info)
        else:
            self.logger.warning(f"Geçersiz video bilgisi alındı: {video_info}")

        self.update_format_options()

    def process_video_info(self, video_info):
        if not video_info or 'error' in video_info:
            QMessageBox.warning(self, "Hata", "Video bilgileri alınamadı.")
            return

        self.temp_video_info.clear()
        self.temp_video_info.append(video_info)
        self.add_video_to_table(video_info)
        self.video_count_label.setText(f"Toplam video sayısı: {len(self.temp_video_info)}")
        self.status_label.setText("Video bilgileri alındı. İndirilmeye hazır.")
        self.progress_bar.setValue(100)

        self.update_format_options()
        self.logger.debug(f"İşlenmiş video bilgileri: {video_info['title']}")

    def add_video_to_table(self, video_info):
        self.video_table.setRowCount(0)  # Mevcut satırları temizle
        row_position = self.video_table.rowCount()
        self.video_table.insertRow(row_position)

        # Checkbox
        checkbox = QTableWidgetItem()
        checkbox.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        checkbox.setCheckState(Qt.CheckState.Checked)
        self.video_table.setItem(row_position, 0, checkbox)

        # Title
        self.video_table.setItem(row_position, 1, QTableWidgetItem(video_info.get('title', 'Bilinmeyen')))

        # Duration
        self.video_table.setItem(row_position, 2, QTableWidgetItem(video_info.get('duration_string', '00:00')))

        # Status
        self.video_table.setItem(row_position, 3, QTableWidgetItem("Hazır"))

        self.logger.debug(f"Video tabloya eklendi: {video_info.get('title', 'Bilinmeyen')}")

    def update_format_options(self):
        self.format_combo.clear()
        self.format_combo.addItems(["Video", "Ses"])
        self.update_quality_options()

    def update_quality_options(self):
        self.quality_combo.clear()
        selected_format = self.format_combo.currentText()

        if self.temp_video_info:
            video_info = self.temp_video_info[0]
            video_formats, audio_formats = self.downloader.get_available_formats(video_info)

            if selected_format == "Video":
                for format_note, format_id in video_formats:
                    self.quality_combo.addItem(format_note, format_id)
            else:
                for format_note, format_id in audio_formats:
                    self.quality_combo.addItem(format_note, format_id)
                # Ses için en iyi kalite seçeneğini ekleyelim
                self.quality_combo.insertItem(0, "En İyi Ses Kalitesi", "bestaudio/best")
        else:
            self.quality_combo.addItem("Kalite seçeneği bulunamadı")

        self.logger.debug(
            f"Kalite seçenekleri güncellendi. Seçenekler: {[self.quality_combo.itemText(i) for i in range(self.quality_combo.count())]}")

    def update_video_selection(self, item):
        if item.column() == 0:
            row = item.row()
            is_checked = item.checkState() == Qt.CheckState.Checked
            if 0 <= row < len(self.temp_video_info):
                self.temp_video_info[row]['selected'] = is_checked
                self.update_video_status()
            else:
                self.logger.error(
                    f"Hata: Geçersiz satır indeksi {row}. temp_video_info uzunluğu: {len(self.temp_video_info)}")

    def update_video_status(self):
        selected_count = sum(1 for video in self.temp_video_info if video.get('selected', False))
        total_duration = sum(self.get_duration_seconds(video.get('duration', '00:00'))
                             for video in self.temp_video_info if video.get('selected', False))

        status_text = f"Seçili video sayısı: {selected_count} | "
        status_text += f"Seçili video süresi: {self.format_duration(total_duration)}"
        self.video_count_label.setText(status_text)

    def update_video_count_label(self):
        count = len(self.temp_video_info)
        self.video_count_label.setText(f"Toplam video sayısı: {count}")

    def get_duration_seconds(self, duration_str):
        parts = duration_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0

    def format_duration(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def on_worker_finish(self):
        self.status_label.setText("Bilgi alma işlemi tamamlandı.")
        self.progress_bar.setValue(100)
        self.update_format_options()
        self.update_video_count_label()
        self.logger.debug("Worker tamamlandı. Format ve kalite seçenekleri güncellendi.")

    def start_download(self):
        if not self.temp_video_info:
            QMessageBox.warning(self, "Hata", "Lütfen önce bir video veya playlist seçin.")
            return

        output_path = self.file_path_input.text()
        if not output_path:
            QMessageBox.warning(self, "Hata", "Lütfen bir indirme konumu seçin.")
            return

        selected_format = self.format_combo.currentText()
        selected_quality = self.quality_combo.currentData()

        selected_videos = [video for video in self.temp_video_info if video.get('selected', True)]

        if not selected_videos:
            QMessageBox.warning(self, "Hata", "Lütfen en az bir video seçin.")
            return

        for index, video in enumerate(selected_videos):
            url = video.get('webpage_url')
            if not url:
                self.logger.error(f"Video URL'si bulunamadı: {video.get('title')}")
                continue

            if "Video" in selected_format:
                format_id = selected_quality
            else:
                format_id = 'bestaudio/best'

            self.downloader.download_video(url, format_id, output_path)

            # Tabloyu güncelle
            for row in range(self.video_table.rowCount()):
                if self.video_table.item(row, 1).text() == video.get('title'):
                    self.video_table.item(row, 3).setText("İndiriliyor")
                    self.video_table.item(row, 3).setBackground(Qt.GlobalColor.yellow)
                    break

        self.logger.debug(f"İndirme başlatıldı: {len(selected_videos)} video")

    def get_format_id(self, video_info, quality):
        for format in video_info.get('formats', []):
            if f"{format.get('height')}p" in quality and format.get('vcodec') != 'none':
                return format['format_id']
        return 'bestvideo+bestaudio/best'

    def update_download_progress(self, filename, downloaded, total):
        progress = (downloaded / total) * 100 if total > 0 else 0
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(f"İndiriliyor: {filename} - %{progress:.1f}")

        speed = downloaded / (time.time() - self.download_start_time) if hasattr(self, 'download_start_time') else 0
        remaining_time = (total - downloaded) / speed if speed > 0 else 0

        self.speed_label.setText(f"İndirme Hızı: {self.format_size(speed)}/s")
        self.time_label.setText(f"Tahmini Süre: {self.format_time(remaining_time)}")

    @staticmethod
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @staticmethod
    def format_time(seconds):
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}s {minutes}d {seconds}s"
        elif minutes > 0:
            return f"{minutes}d {seconds}s"
        else:
            return f"{seconds}s"

    def update_download_status(self, filename, status):
        for row in range(self.video_table.rowCount()):
            if self.video_table.item(row, 1).text() in filename:
                self.video_table.item(row, 3).setText(status)
                if status == "Tamamlandı":
                    self.video_table.item(row, 3).setBackground(Qt.GlobalColor.green)
                elif status == "Hata":
                    self.video_table.item(row, 3).setBackground(Qt.GlobalColor.red)

    def on_download_finished(self, filename):
        self.logger.info(f"İndirme tamamlandı: {filename}")
        self.progress_signal.emit("İndirme tamamlandı", 100, 100, {"filename": filename, "status": "Tamamlandı"})

    def on_download_error(self, error, filename):
        self.logger.error(f"İndirme hatası: {error}, Dosya: {filename}")
        self.progress_signal.emit(f"İndirme hatası: {error}", 0, 100, {"filename": filename, "status": "Hata"})