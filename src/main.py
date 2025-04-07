import tkinter as tk
from tkinter import ttk
import threading
from screen_analyzer import ScreenAnalyzer

class AnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Screen Video Stream Analyzer")
        self.root.geometry("400x300")
        
        self.analyzer = ScreenAnalyzer()
        self.analysis_thread = None
        
        # Create widgets
        self.create_widgets()
    
    def create_widgets(self):
        # FPS selection
        fps_frame = ttk.LabelFrame(self.root, text="FPS Selection")
        fps_frame.pack(fill="x", padx=10, pady=10)
        
        self.fps_var = tk.IntVar(value=30)
        
        for fps in self.analyzer.fps_options:
            ttk.Radiobutton(fps_frame, text=str(fps), value=fps, 
                            variable=self.fps_var, command=self.set_fps).pack(side=tk.LEFT, padx=10)
        
        # Control buttons
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        self.select_roi_btn = ttk.Button(control_frame, text="Select Region", 
                                        command=self.select_roi)
        self.select_roi_btn.pack(fill="x", pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="Start Analysis", 
                                    command=self.start_analysis, state=tk.DISABLED)
        self.start_btn.pack(fill="x", pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Analysis", 
                                    command=self.stop_analysis, state=tk.DISABLED)
        self.stop_btn.pack(fill="x", pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, 
                 font=("Helvetica", 10, "italic")).pack(pady=10)
    
    def set_fps(self):
        fps = self.fps_var.get()
        self.analyzer.set_fps(fps)
        self.status_var.set(f"FPS set to {fps}")
    
    def select_roi(self):
        self.status_var.set("Selecting region...")
        self.select_roi_btn.config(state=tk.DISABLED)
        
        # Run in thread to prevent GUI freezing
        def roi_thread():
            self.analyzer.select_roi()
            self.root.after(0, self.on_roi_selected)
        
        threading.Thread(target=roi_thread).start()
    
    def on_roi_selected(self):
        if self.analyzer.roi_selected:
            self.status_var.set(f"Region selected: ({self.analyzer.x1}, {self.analyzer.y1}) to ({self.analyzer.x2}, {self.analyzer.y2})")
            self.start_btn.config(state=tk.NORMAL)
        else:
            self.status_var.set("Region selection canceled")
        
        self.select_roi_btn.config(state=tk.NORMAL)
    
    def start_analysis(self):
        if self.analysis_thread and self.analysis_thread.is_alive():
            return
            
        self.status_var.set(f"Starting analysis at {self.analyzer.current_fps} FPS...")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        
        # Run analysis in separate thread
        self.analysis_thread = threading.Thread(target=self.analyzer.start_analysis)
        self.analysis_thread.daemon = True
        self.analysis_thread.start()
    
    def stop_analysis(self):
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analyzer.stop_analysis()
            self.analysis_thread.join(timeout=1.0)
            
        self.status_var.set("Analysis stopped")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def on_closing(self):
        if self.analysis_thread and self.analysis_thread.is_alive():
            self.analyzer.stop_analysis()
            self.analysis_thread.join(timeout=1.0)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AnalyzerGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()