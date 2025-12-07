"""
Scheduled version that runs continuously with intervals.
Use this if you want the container to stay running and check periodically.
"""
import time
from datetime import datetime
from upload_videos import get_first_pending_row, upload_video, update_sheet_row

# Run every X hours
RUN_INTERVAL_HOURS = 6

def main():
    print(f"=== Scheduled uploader started at {datetime.now()} ===")
    print(f"Will check for pending videos every {RUN_INTERVAL_HOURS} hours")
    
    while True:
        try:
            print(f"\n=== Checking for pending videos at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
            
            pending = get_first_pending_row()
            if not pending:
                print("No pending videos found.")
            else:
                row_number, row_data = pending
                print(f"Processing row {row_number}: {row_data.get('title', 'No title')}")
                
                try:
                    upload_video(row_data)
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    update_sheet_row(row_number, "posted", now_str)
                    print(f"✓ Sheet updated for row {row_number}")
                    print(f"=== Upload completed successfully at {now_str} ===")
                except Exception as e:
                    print(f"✗ Upload failed: {str(e)}")
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        update_sheet_row(row_number, f"error: {str(e)[:50]}", now_str)
                    except:
                        pass
            
            # Wait for next run
            sleep_seconds = RUN_INTERVAL_HOURS * 3600
            next_run = datetime.now().timestamp() + sleep_seconds
            next_run_time = datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')
            print(f"\nSleeping until {next_run_time}...")
            time.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            print("\n=== Scheduler stopped by user ===")
            break
        except Exception as e:
            print(f"✗ Unexpected error: {str(e)}")
            print("Waiting 5 minutes before retry...")
            time.sleep(300)

if __name__ == "__main__":
    main()
