import sys
import time
from screen_analyzer import ScreenAnalyzer

def main():
    analyzer = ScreenAnalyzer()
    
    print("Welcome to Screen Video Stream Analyzer (Console Edition)")
    print("-" * 50)
    
    # Set FPS
    print("\nAvailable FPS options:")
    for i, fps in enumerate(analyzer.fps_options):
        print(f"{i+1}. {fps} FPS")
    
    while True:
        try:
            choice = int(input("\nSelect FPS (1-4): "))
            if 1 <= choice <= 4:
                fps = analyzer.fps_options[choice-1]
                analyzer.set_fps(fps)
                break
            else:
                print("Invalid choice. Please enter a number between 1 and 4.")
        except ValueError:
            print("Please enter a valid number.")
    
    # Select ROI
    print("\nPress Enter to select the region of interest...")
    input()
    analyzer.select_roi()
    
    if not analyzer.roi_selected:
        print("ROI selection canceled. Exiting.")
        return
    
    # Start analysis
    print("\nPress Ctrl+C to stop the analysis")
    print("Starting analysis...")
    time.sleep(1)
    
    try:
        analyzer.start_analysis()
    except KeyboardInterrupt:
        print("\nStopping analysis...")
    finally:
        analyzer.stop_analysis()
        
    print("\nAnalysis complete. Check the 'reports' directory for results.")

if __name__ == "__main__":
    main()