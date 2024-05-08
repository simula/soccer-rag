# Try to import pandas, if fails, ask the user to install it
try:
    from SoccerNet.Downloader import SoccerNetDownloader
except ImportError:
    print("SoccerNet package not found. Please install it by running 'pip install soccernet'")
    exit(1)

from src.database import process_json_files,fill_Augmented_Team, fill_Augmented_League
import threading

mySoccerNetDownloader = SoccerNetDownloader(LocalDirectory="data/dataset/SoccerNet")

# Download function
def download_labels(file_name):
    try:
        mySoccerNetDownloader.downloadGames(files=[file_name], split=["train", "valid", "test"])
    except Exception as e:
        print(f"Error downloading {file_name}: {e}")


# Create threads for downloading different sets of labels
thread_v2 = threading.Thread(target=download_labels, args=("Labels-v2.json",))
thread_caption = threading.Thread(target=download_labels, args=("Labels-caption.json",))

# Start the threads
thread_v2.start()
thread_caption.start()

# Wait for both threads to complete
thread_v2.join()
thread_caption.join()

print("All files downloaded successfully!")
print("Creating database..")



process_json_files("data/dataset/SoccerNet/")
fill_Augmented_Team("data/Dataset/augmented_teams.csv")
fill_Augmented_League("data/Dataset/augmented_leagues.csv")