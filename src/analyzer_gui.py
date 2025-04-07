import sys
import os
import cv2
import numpy as np
import time
import pyautogui
import datetime
import threading
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, 
                             QGroupBox, QSlider, QCheckBox, QFileDialog, QStatusBar)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QImage, QPixmap

class ScreenAnalyzerThread(QThread):
    update_signal = pyqtSignal(object)
    report_signal = pyqtSignal(str, object)
    
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.running = False
        self.frame_buffer = []
        self.report = []
        
    def run(self):
        self.running = True
        self.frame_buffer = []
        self.report = []
        
        buffer_size = 3
        
        try:
            while self.running:
                loop_start = time.time()
                
                # Захват экрана
                x1, y1, x2, y2 = self.settings['region']
                screenshot = pyautogui.screenshot(region=(x1, y1, x2-x1, y2-y1))
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Добавляем в буфер с отметкой времени
                current_time = time.time()
                self.frame_buffer.append({
                    "frame": frame.copy(),
                    "time": current_time
                })
                
                # Ограничиваем размер буфера
                if len(self.frame_buffer) > buffer_size:
                    self.frame_buffer.pop(0)
                
                # Анализ дефектов если включено
                analysis_results = []
                
                # 1. Обнаружение зеленых пикселей
                if self.settings['detect_green']:
                    green_detected = self.detect_green_pixels(frame)
                    if green_detected:
                        analysis_results.append("Green pixels")
                
                # 2. Обнаружение выпадения кадров
                if self.settings['detect_frame_drops'] and len(self.frame_buffer) >= 2:
                    frame_drop_detected = self.detect_frame_drops()
                    if frame_drop_detected:
                        analysis_results.append("Frame drop")
                
                # 3. Обнаружение разрывов изображения
                if self.settings['detect_tearing'] and len(self.frame_buffer) >= 2:
                    tearing_detected = self.detect_image_tearing(frame)
                    if tearing_detected:
                        analysis_results.append("Image tearing")
                
                # Отправляем текущий кадр в GUI
                frame_data = {
                    "frame": frame,
                    "analysis": analysis_results
                }
                self.update_signal.emit(frame_data)
                
                # Расчет времени сна для поддержания FPS
                fps = self.settings['fps']
                process_time = time.time() - loop_start
                sleep_time = (1.0 / fps) - process_time
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except Exception as e:
            print(f"Error in analyzer thread: {str(e)}")
        
        self.running = False
    
    def detect_green_pixels(self, frame):
        # Конвертация в HSV для лучшего обнаружения цвета
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Диапазон зеленого цвета в HSV
        lower_green = np.array([35, 100, 100])
        upper_green = np.array([85, 255, 255])
        
        # Маска для выделения зеленого цвета
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Подсчет зеленых пикселей
        green_pixel_count = cv2.countNonZero(mask)
        
        # Если зеленых пикселей больше порога
        threshold = self.settings['green_threshold']
        if green_pixel_count > threshold:
            frame_with_mask = frame.copy()
            green_areas = cv2.bitwise_and(frame_with_mask, frame_with_mask, mask=mask)
            
            # Добавляем области зеленого цвета на копию кадра
            alpha = 0.5
            cv2.addWeighted(green_areas, alpha, frame_with_mask, 1 - alpha, 0, frame_with_mask)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.report.append({
                "timestamp": timestamp,
                "type": "green_pixels",
                "details": f"Detected {green_pixel_count} green pixels",
                "frame": frame_with_mask.copy()
            })
            
            # Отправляем сигнал о найденном дефекте
            self.report_signal.emit(f"Green pixels: {green_pixel_count}", frame_with_mask)
            return True
        return False
    
    def detect_frame_drops(self):
        # Проверяем интервал между кадрами
        expected_interval = 1.0 / self.settings['fps']
        actual_interval = self.frame_buffer[-1]["time"] - self.frame_buffer[-2]["time"]
        
        # Порог определения пропуска кадров (коэффициент)
        threshold = self.settings['frame_drop_threshold']
        
        if actual_interval > (expected_interval * threshold):
            frame_with_text = self.frame_buffer[-1]["frame"].copy()
            text = f"Drop: {actual_interval:.4f}s vs expected {expected_interval:.4f}s"
            cv2.putText(frame_with_text, text, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.8, (0, 0, 255), 2)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.report.append({
                "timestamp": timestamp,
                "type": "frame_drop",
                "details": f"Expected: {expected_interval:.4f}s, Actual: {actual_interval:.4f}s",
                "frame": frame_with_text.copy()
            })
            
            # Отправляем сигнал о найденном дефекте
            self.report_signal.emit(f"Frame drop: {actual_interval:.4f}s", frame_with_text)
            return True
        return False
    
    def detect_image_tearing(self, frame):
        # Получаем предыдущий кадр из буфера
        prev_frame = self.frame_buffer[-2]["frame"]
        
        # Конвертация в оттенки серого
        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Вычисляем разницу между кадрами
        diff = cv2.absdiff(gray1, gray2)
        
        # Пороговая обработка разницы
        threshold_value = self.settings['tearing_threshold']
        _, thresh = cv2.threshold(diff, threshold_value, 255, cv2.THRESH_BINARY)
        
        # Находим контуры на изображении разницы
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Фильтруем контуры по размеру
        min_contour_area = self.settings['tearing_min_area']
        large_contours = [c for c in contours if cv2.contourArea(c) > min_contour_area]
        
        if len(large_contours) > 0:
            # Рисуем контуры на копии кадра
            frame_with_contours = frame.copy()
            cv2.drawContours(frame_with_contours, large_contours, -1, (0, 0, 255), 2)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.report.append({
                "timestamp": timestamp,
                "type": "image_tearing",
                "details": f"Detected {len(large_contours)} potential tears",
                "frame": frame_with_contours.copy()
            })
            
            # Отправляем сигнал о найденном дефекте
            self.report_signal.emit(f"Image tearing: {len(large_contours)} areas", frame_with_contours)
            return True
        return False
    
    def stop(self):
        self.running = False
        self.wait()
    
    def save_report(self, output_dir):
        # Сохраняем отчет в файл
        if not self.report:
            return "No issues to report"
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(output_dir, f"report_{timestamp}")
        os.makedirs(report_dir, exist_ok=True)
        
        with open(os.path.join(report_dir, "summary.txt"), "w") as f:
            f.write(f"Screen Analysis Report - {timestamp}\n")
            f.write(f"FPS: {self.settings['fps']}\n")
            x1, y1, x2, y2 = self.settings['region']
            f.write(f"ROI: ({x1}, {y1}) to ({x2}, {y2})\n\n")
            
            f.write("Settings:\n")
            f.write(f"Green pixel threshold: {self.settings['green_threshold']}\n")
            f.write(f"Frame drop threshold: {self.settings['frame_drop_threshold']}\n")
            f.write(f"Tearing threshold: {self.settings['tearing_threshold']}\n")
            f.write(f"Tearing min area: {self.settings['tearing_min_area']}\n\n")
            
            for i, incident in enumerate(self.report):
                f.write(f"Incident #{i+1}\n")
                f.write(f"Timestamp: {incident['timestamp']}\n")
                f.write(f"Type: {incident['type']}\n")
                f.write(f"Details: {incident['details']}\n\n")
                
                # Сохраняем кадр
                cv2.imwrite(os.path.join(report_dir, f"incident_{i+1}.png"), incident["frame"])
        
        return report_dir


class RegionSelector(QMainWindow):
    region_selected = pyqtSignal(tuple)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Region")
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        screen_width, screen_height = pyautogui.size()
        self.setGeometry(0, 0, screen_width, screen_height)
        
        self.start_point = None
        self.end_point = None
        self.selecting = False
        
        self.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
        self.setWindowOpacity(0.3)
        
        label = QLabel("Click and drag to select region, then press Enter", self)
        label.setStyleSheet("color: white; font-size: 24px; background-color: rgba(0, 0, 0, 100);")
        label.setAlignment(Qt.AlignCenter)
        label.setGeometry(0, 0, screen_width, 50)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if self.start_point and self.end_point:
                x1 = min(self.start_point.x(), self.end_point.x())
                y1 = min(self.start_point.y(), self.end_point.y())
                x2 = max(self.start_point.x(), self.end_point.x())
                y2 = max(self.start_point.y(), self.end_point.y())
                
                # Убедимся, что область имеет минимальный размер
                if x2 - x1 > 10 and y2 - y1 > 10:
                    self.region_selected.emit((x1, y1, x2, y2))
                    self.close()
                
        elif event.key() == Qt.Key_Escape:
            self.close()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = None
            self.selecting = True
            self.update()
    
    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.end_point = event.pos()
            self.selecting = False
            self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if self.start_point and self.end_point:
            from PyQt5.QtGui import QPainter, QColor, QPen
            
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.SolidLine))
            
            x = min(self.start_point.x(), self.end_point.x())
            y = min(self.start_point.y(), self.end_point.y())
            width = abs(self.end_point.x() - self.start_point.x())
            height = abs(self.end_point.y() - self.start_point.y())
            
            painter.drawRect(x, y, width, height)


class VideoStreamAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Stream Analyzer")
        self.setGeometry(100, 100, 1280, 720)
        
        # Создаем папку для отчетов
        self.output_dir = "reports"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Настройки по умолчанию
        self.settings = {
            'region': (0, 0, 640, 480),  # x1, y1, x2, y2
            'fps': 30,
            'detect_green': True,
            'detect_frame_drops': True,
            'detect_tearing': True,
            'green_threshold': 100,
            'frame_drop_threshold': 1.5,  # коэффициент от ожидаемого интервала
            'tearing_threshold': 30,      # порог для обнаружения разницы между кадрами
            'tearing_min_area': 500       # минимальная площадь контура для обнаружения разрыва
        }
        
        # Инициализация UI
        self.init_ui()
        
        # Создаем поток анализа
        self.analyzer_thread = None
        self.is_analyzing = False
    
    def init_ui(self):
        # Создаем центральный виджет
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QHBoxLayout(central_widget)
        
        # Левая панель с настройками
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(15)
        
        # 1. Группа настроек области
        region_group = QGroupBox("Region Settings")
        region_layout = QVBoxLayout(region_group)
        
        self.region_label = QLabel(f"Selected region: ({self.settings['region'][0]}, {self.settings['region'][1]}) - "
                                   f"({self.settings['region'][2]}, {self.settings['region'][3]})")
        region_layout.addWidget(self.region_label)
        
        select_region_btn = QPushButton("Select Region")
        select_region_btn.clicked.connect(self.select_region)
        region_layout.addWidget(select_region_btn)
        
        # Предустановленные разрешения
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Preset Resolutions:"))
        
        resolution_combo = QComboBox()
        resolution_combo.addItems(["640x480", "1280x720", "1920x1080", "Custom"])
        resolution_combo.currentTextChanged.connect(self.preset_resolution_changed)
        resolution_layout.addWidget(resolution_combo)
        
        region_layout.addLayout(resolution_layout)
        settings_layout.addWidget(region_group)
        
        # 2. Группа настроек FPS
        fps_group = QGroupBox("FPS Settings")
        fps_layout = QVBoxLayout(fps_group)
        
        fps_layout.addWidget(QLabel("Select FPS:"))
        fps_combo = QComboBox()
        fps_combo.addItems(["15", "25", "30", "60"])
        fps_combo.setCurrentText(str(self.settings['fps']))
        fps_combo.currentTextChanged.connect(lambda value: self.update_setting('fps', int(value)))
        fps_layout.addWidget(fps_combo)
        
        settings_layout.addWidget(fps_group)
        
        # 3. Группа настроек обнаружения
        detection_group = QGroupBox("Detection Settings")
        detection_layout = QVBoxLayout(detection_group)
        
        # Включение/выключение детекторов
        self.green_check = QCheckBox("Detect Green Pixels")
        self.green_check.setChecked(self.settings['detect_green'])
        self.green_check.stateChanged.connect(
            lambda state: self.update_setting('detect_green', state == Qt.Checked))
        detection_layout.addWidget(self.green_check)
        
        self.frame_drop_check = QCheckBox("Detect Frame Drops")
        self.frame_drop_check.setChecked(self.settings['detect_frame_drops'])
        self.frame_drop_check.stateChanged.connect(
            lambda state: self.update_setting('detect_frame_drops', state == Qt.Checked))
        detection_layout.addWidget(self.frame_drop_check)
        
        self.tearing_check = QCheckBox("Detect Image Tearing")
        self.tearing_check.setChecked(self.settings['detect_tearing'])
        self.tearing_check.stateChanged.connect(
            lambda state: self.update_setting('detect_tearing', state == Qt.Checked))
        detection_layout.addWidget(self.tearing_check)
        
        # Настройки порогов
        detection_layout.addWidget(QLabel("Green Pixel Threshold:"))
        green_threshold = QSpinBox()
        green_threshold.setRange(10, 10000)
        green_threshold.setValue(self.settings['green_threshold'])
        green_threshold.valueChanged.connect(
            lambda value: self.update_setting('green_threshold', value))
        detection_layout.addWidget(green_threshold)
        
        detection_layout.addWidget(QLabel("Frame Drop Threshold (multiplier):"))
        drop_threshold = QDoubleSpinBox()
        drop_threshold.setRange(1.1, 5.0)
        drop_threshold.setSingleStep(0.1)
        drop_threshold.setValue(self.settings['frame_drop_threshold'])
        drop_threshold.valueChanged.connect(
            lambda value: self.update_setting('frame_drop_threshold', value))
        detection_layout.addWidget(drop_threshold)
        
        detection_layout.addWidget(QLabel("Tearing Detection Threshold:"))
        tearing_threshold = QSpinBox()
        tearing_threshold.setRange(5, 100)
        tearing_threshold.setValue(self.settings['tearing_threshold'])
        tearing_threshold.valueChanged.connect(
            lambda value: self.update_setting('tearing_threshold', value))
        detection_layout.addWidget(tearing_threshold)
        
        detection_layout.addWidget(QLabel("Tearing Minimum Area:"))
        tearing_area = QSpinBox()
        tearing_area.setRange(50, 5000)
        tearing_area.setValue(self.settings['tearing_min_area'])
        tearing_area.valueChanged.connect(
            lambda value: self.update_setting('tearing_min_area', value))
        detection_layout.addWidget(tearing_area)
        
        settings_layout.addWidget(detection_group)
        
        # Кнопки управления
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Analysis")
        self.start_btn.clicked.connect(self.toggle_analysis)
        control_layout.addWidget(self.start_btn)
        
        save_report_btn = QPushButton("Save Report")
        save_report_btn.clicked.connect(self.save_report)
        control_layout.addWidget(save_report_btn)
        
        settings_layout.addLayout(control_layout)
        settings_layout.addStretch()
        
        # Правая панель с превью видео
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #222222;")
        self.video_label.setMinimumSize(640, 480)
        preview_layout.addWidget(self.video_label)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: #008800;")
        preview_layout.addWidget(self.status_label)
        
        # Добавляем виджеты в основной layout
        main_layout.addWidget(settings_widget, 1)
        main_layout.addWidget(preview_widget, 2)
        
        # Создаем статус бар
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
    
    def select_region(self):
        self.setVisible(False)
        time.sleep(0.5)  # Даем время для скрытия основного окна
        
        # Создаем селектор области
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self.on_region_selected)
        self.region_selector.show()
        
    def on_region_selected(self, region):
        self.settings['region'] = region
        self.region_label.setText(f"Selected region: ({region[0]}, {region[1]}) - ({region[2]}, {region[3]})")
        self.setVisible(True)
    
    def preset_resolution_changed(self, resolution):
        if resolution == "Custom":
            self.select_region()
            return
            
        # Парсим разрешение
        width, height = map(int, resolution.split('x'))
        
        # Центрируем область на экране
        screen_width, screen_height = pyautogui.size()
        x1 = (screen_width - width) // 2
        y1 = (screen_height - height) // 2
        x2 = x1 + width
        y2 = y1 + height
        
        self.settings['region'] = (x1, y1, x2, y2)
        self.region_label.setText(f"Selected region: ({x1}, {y1}) - ({x2}, {y2})")
    
    def update_setting(self, key, value):
        self.settings[key] = value
    
    def toggle_analysis(self):
        if not self.is_analyzing:
            self.start_analysis()
        else:
            self.stop_analysis()
    
    def start_analysis(self):
        # Проверяем, что область выбрана
        x1, y1, x2, y2 = self.settings['region']
        if x2 - x1 < 10 or y2 - y1 < 10:
            self.statusBar.showMessage("Please select a valid region first")
            return
        
        # Создаем и запускаем поток анализа
        self.analyzer_thread = ScreenAnalyzerThread(self.settings)
        self.analyzer_thread.update_signal.connect(self.update_preview)
        self.analyzer_thread.report_signal.connect(self.on_defect_detected)
        self.analyzer_thread.start()
        
        self.is_analyzing = True
        self.start_btn.setText("Stop Analysis")
        self.status_label.setText("Analyzing...")
        self.statusBar.showMessage(f"Analysis started at {self.settings['fps']} FPS")
    
    def stop_analysis(self):
        if self.analyzer_thread and self.analyzer_thread.isRunning():
            self.analyzer_thread.stop()
            self.analyzer_thread = None
        
        self.is_analyzing = False
        self.start_btn.setText("Start Analysis")
        self.status_label.setText("Ready")
        self.statusBar.showMessage("Analysis stopped")
    
    def update_preview(self, frame_data):
        frame = frame_data["frame"]
        analysis_results = frame_data["analysis"]
        
        # Конвертируем кадр для отображения в QLabel
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_img)
        
        # Масштабируем изображение до размера QLabel, сохраняя пропорции
        pixmap = pixmap.scaled(self.video_label.width(), self.video_label.height(), 
                              Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        self.video_label.setPixmap(pixmap)
        
        # Обновляем статус, если обнаружены дефекты
        if analysis_results:
            status_text = ", ".join(analysis_results)
            self.status_label.setText(f"Detected: {status_text}")
            self.status_label.setStyleSheet("font-weight: bold; color: #FF0000;")
        else:
            self.status_label.setText("Analyzing...")
            self.status_label.setStyleSheet("font-weight: bold; color: #008800;")
    
    def on_defect_detected(self, message, frame):
        self.statusBar.showMessage(message, 3000)
    
    def save_report(self):
        if not self.analyzer_thread:
            self.statusBar.showMessage("No analysis data to save")
            return
        
        report_path = self.analyzer_thread.save_report(self.output_dir)
        if report_path == "No issues to report":
            self.statusBar.showMessage("No issues detected, no report generated")
        else:
            self.statusBar.showMessage(f"Report saved to {report_path}")
    
    def closeEvent(self, event):
        self.stop_analysis()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VideoStreamAnalyzerApp()
    window.show()
    sys.exit(app.exec_())