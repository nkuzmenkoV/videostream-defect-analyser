import cv2
import numpy as np
import time
import pyautogui
import datetime
import os

def main():
    # Создаем директорию для отчетов
    output_dir = "reports"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Фиксированные параметры
    fps = 30
    print(f"Using fixed FPS: {fps}")
    
    # Захват всего экрана
    screen_width, screen_height = pyautogui.size()
    print(f"Screen size: {screen_width}x{screen_height}")
    
    # Создаем уменьшенную область для демонстрации
    # Возьмем верхний левый угол размером 1280x720 (720p)
    x1, y1, w, h = 0, 0, 1280, 720
    print(f"Using region: ({x1}, {y1}) to ({x1+w}, {y1+h})")
    
    # Буфер для обнаружения выпадения кадров
    frame_buffer = []
    buffer_size = 3
    report = []
    running = True
    
    try:
        print("Starting analysis... Press Ctrl+C to stop")
        
        while running:
            loop_start = time.time()
            
            # Захват экрана
            screenshot = pyautogui.screenshot(region=(x1, y1, w, h))
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Добавляем в буфер с отметкой времени
            current_time = time.time()
            frame_buffer.append({
                "frame": frame.copy(),
                "time": current_time
            })
            
            # Ограничиваем размер буфера
            if len(frame_buffer) > buffer_size:
                frame_buffer.pop(0)
            
            # 1. Обнаружение зеленых пикселей
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_green = np.array([35, 100, 100])
            upper_green = np.array([85, 255, 255])
            mask = cv2.inRange(hsv, lower_green, upper_green)
            green_pixel_count = cv2.countNonZero(mask)
            
            if green_pixel_count > 100:  # Порог срабатывания
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                report.append({
                    "timestamp": timestamp,
                    "type": "green_pixels",
                    "details": f"Detected {green_pixel_count} green pixels",
                    "frame": frame.copy()
                })
                print(f"Green pixels detected: {green_pixel_count}")
            
            # 2. Обнаружение выпадения кадров
            if len(frame_buffer) >= 2:
                expected_interval = 1.0 / fps
                actual_interval = frame_buffer[-1]["time"] - frame_buffer[-2]["time"]
                
                if actual_interval > (expected_interval * 1.5):
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    report.append({
                        "timestamp": timestamp,
                        "type": "frame_drop",
                        "details": f"Expected: {expected_interval:.4f}s, Actual: {actual_interval:.4f}s",
                        "frame": frame.copy()
                    })
                    print(f"Frame drop detected: {actual_interval:.4f}s vs expected {expected_interval:.4f}s")
            
            # 3. Обнаружение разрывов изображения
            if len(frame_buffer) >= 2:
                prev_frame = frame_buffer[-2]["frame"]
                gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                diff = cv2.absdiff(gray1, gray2)
                _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
                
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                large_contours = [c for c in contours if cv2.contourArea(c) > 500]
                
                if len(large_contours) > 0:
                    frame_with_contours = frame.copy()
                    cv2.drawContours(frame_with_contours, large_contours, -1, (0, 0, 255), 2)
                    
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    report.append({
                        "timestamp": timestamp,
                        "type": "image_tearing",
                        "details": f"Detected {len(large_contours)} potential tears",
                        "frame": frame_with_contours
                    })
                    print(f"Image tearing detected: {len(large_contours)} regions")
            
            # Показываем кадр
            text = f"FPS: {fps} | Press 'q' to quit"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow("Screen Analysis", frame)
            
            # Проверяем нажатие клавиши выхода
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            
            # Поддержание FPS
            process_time = time.time() - loop_start
            sleep_time = (1.0 / fps) - process_time
            
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("\nAnalysis stopped by user")
    finally:
        cv2.destroyAllWindows()
        
        # Сохраняем отчет
        if report:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_dir = os.path.join(output_dir, f"report_{timestamp}")
            os.makedirs(report_dir, exist_ok=True)
            
            with open(os.path.join(report_dir, "summary.txt"), "w") as f:
                f.write(f"Screen Analysis Report - {timestamp}\n")
                f.write(f"FPS: {fps}\n")
                f.write(f"ROI: ({x1}, {y1}) to ({x1+w}, {y1+h})\n\n")
                
                for i, incident in enumerate(report):
                    f.write(f"Incident #{i+1}\n")
                    f.write(f"Timestamp: {incident['timestamp']}\n")
                    f.write(f"Type: {incident['type']}\n")
                    f.write(f"Details: {incident['details']}\n\n")
                    
                    # Сохраняем кадр
                    cv2.imwrite(os.path.join(report_dir, f"incident_{i+1}.png"), incident["frame"])
            
            print(f"\nReport saved to {report_dir}")
        else:
            print("\nNo issues detected, no report generated")

if __name__ == "__main__":
    main()