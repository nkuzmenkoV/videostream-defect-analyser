import cv2
import numpy as np
import time
import pyautogui
import datetime
import os

class ScreenAnalyzer:
    def __init__(self, output_dir="reports"):
        self.fps_options = [15, 25, 30, 60]
        self.current_fps = 30
        self.x1, self.y1, self.x2, self.y2 = 0, 0, 0, 0
        self.roi_selected = False
        self.running = False
        self.frame_buffer = []
        self.buffer_size = 3  # For frame comparison
        self.report = []
        self.output_dir = output_dir
        
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def select_roi(self):
        """Allow user to select region of interest"""
        print("Please select the region of interest")
        print("Click and drag to select area, then press Enter")
        
        # Use OpenCV to create a window for ROI selection
        img = pyautogui.screenshot()
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        roi = cv2.selectROI("Select Region", img)
        cv2.destroyAllWindows()
        
        self.x1, self.y1, w, h = roi
        self.x2, self.y2 = self.x1 + w, self.y1 + h
        self.roi_selected = True
        print(f"ROI selected: ({self.x1}, {self.y1}) to ({self.x2}, {self.y2})")
    
    def set_fps(self, fps):
        """Set the capture framerate"""
        if fps in self.fps_options:
            self.current_fps = fps
            print(f"FPS set to {fps}")
        else:
            print(f"Invalid FPS. Please choose from {self.fps_options}")
    
    def capture_screen(self):
        """Capture the selected region of screen"""
        if not self.roi_selected:
            print("Please select ROI first")
            return None
        
        screenshot = pyautogui.screenshot(region=(self.x1, self.y1, 
                                               self.x2 - self.x1, 
                                               self.y2 - self.y1))
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    def detect_green_pixels(self, frame):
        """Detect green pixels in the frame"""
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Define range of green color in HSV
        lower_green = np.array([35, 100, 100])
        upper_green = np.array([85, 255, 255])
        
        # Threshold the HSV image to get only green colors
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Count green pixels
        green_pixel_count = cv2.countNonZero(mask)
        
        # If green pixels exceed threshold
        if green_pixel_count > 100:  # Adjust threshold as needed
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.report.append({
                "timestamp": timestamp,
                "type": "green_pixels",
                "details": f"Detected {green_pixel_count} green pixels",
                "frame": frame.copy()
            })
            print(f"Green pixels detected: {green_pixel_count}")
            return True
        return False
    
    def detect_frame_drops(self):
        """Detect frame drops by comparing timestamps"""
        if len(self.frame_buffer) < 2:
            return False
            
        expected_interval = 1.0 / self.current_fps
        actual_interval = self.frame_buffer[-1]["time"] - self.frame_buffer[-2]["time"]
        
        # If actual interval is significantly larger than expected
        if actual_interval > (expected_interval * 1.5):
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.report.append({
                "timestamp": timestamp,
                "type": "frame_drop",
                "details": f"Expected: {expected_interval:.4f}s, Actual: {actual_interval:.4f}s",
                "frame": self.frame_buffer[-1]["frame"]
            })
            print(f"Frame drop detected: {actual_interval:.4f}s vs expected {expected_interval:.4f}s")
            return True
        return False
    
    def detect_image_tearing(self, frame):
        """Detect image tearing/artifacts"""
        if len(self.frame_buffer) < 2:
            return False
            
        prev_frame = self.frame_buffer[-1]["frame"]
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference
        diff = cv2.absdiff(gray1, gray2)
        
        # Threshold the difference
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # If large contours found, might indicate tearing
        large_contours = [c for c in contours if cv2.contourArea(c) > 500]
        
        if len(large_contours) > 0:
            # Draw contours on frame copy
            frame_with_contours = frame.copy()
            cv2.drawContours(frame_with_contours, large_contours, -1, (0, 0, 255), 2)
            
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.report.append({
                "timestamp": timestamp,
                "type": "image_tearing",
                "details": f"Detected {len(large_contours)} potential tears",
                "frame": frame_with_contours
            })
            print(f"Image tearing detected: {len(large_contours)} regions")
            return True
        return False
    
    def start_analysis(self):
        """Start analyzing the screen region"""
        if not self.roi_selected:
            print("Please select ROI first")
            return
            
        self.running = True
        self.frame_buffer = []
        self.report = []
        
        print(f"Starting analysis at {self.current_fps} FPS...")
        
        try:
            while self.running:
                loop_start = time.time()
                
                # Capture frame
                frame = self.capture_screen()
                if frame is None:
                    continue
                
                # Store in buffer with timestamp
                self.frame_buffer.append({
                    "frame": frame,
                    "time": time.time()
                })
                
                # Keep buffer size limited
                if len(self.frame_buffer) > self.buffer_size:
                    self.frame_buffer.pop(0)
                
                # Run detections
                self.detect_green_pixels(frame)
                self.detect_frame_drops()
                self.detect_image_tearing(frame)
                
                # Display the frame
                cv2.imshow("Screen Analysis", frame)
                
                # Check for exit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                # Calculate sleep time to maintain FPS
                process_time = time.time() - loop_start
                sleep_time = (1.0 / self.current_fps) - process_time
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            pass
        finally:
            cv2.destroyAllWindows()
            self.running = False
            self.save_report()
    
    def stop_analysis(self):
        """Stop the analysis"""
        self.running = False
        print("Analysis stopped")
    
    def save_report(self):
        """Save the report to a file"""
        if not self.report:
            print("No issues to report")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(self.output_dir, f"report_{timestamp}")
        os.makedirs(report_dir, exist_ok=True)
        
        # Write summary text file
        with open(os.path.join(report_dir, "summary.txt"), "w") as f:
            f.write(f"Screen Analysis Report - {timestamp}\n")
            f.write(f"FPS: {self.current_fps}\n")
            f.write(f"ROI: ({self.x1}, {self.y1}) to ({self.x2}, {self.y2})\n\n")
            
            for i, incident in enumerate(self.report):
                f.write(f"Incident #{i+1}\n")
                f.write(f"Timestamp: {incident['timestamp']}\n")
                f.write(f"Type: {incident['type']}\n")
                f.write(f"Details: {incident['details']}\n\n")
                
                # Save frame
                cv2.imwrite(os.path.join(report_dir, f"incident_{i+1}.png"), incident["frame"])
        
        print(f"Report saved to {report_dir}")