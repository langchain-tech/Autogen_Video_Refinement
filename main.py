import os
from typing import Annotated, List, Optional, Union
import whisper
from moviepy.editor import *
from openai import OpenAI
import autogen
import requests
import tempfile
from pydantic import BaseModel
from dotenv import load_dotenv


### Uncomment import 'pdb' this to use debugger in the app
### Use this code in between any file or function to stop debugger at any point pdb.set_trace()
import pdb

## Used to load .env file
load_dotenv()


# Can change any gpt model as per the available Open-AI subscription
config_list = [
    {
        "model": "gpt-3.5-turbo-0125",
        "api_key": os.getenv("OPENAI_API_KEY"),
    }
]

dic_format = [
    {
        "start": "", "end": "", "transcript": ""
    },
    {
        "start": "", "end": "", "transcript": ""
    }
]

arguments = {"filepath":"...","segments":[{"start":"0","end":"35.0","transcript":"I think it's kind of ridiculous you're not sitting down.."}]}

assistant = autogen.AssistantAgent(
    name="assistant",
    system_message="For coding tasks, only use the functions you have been provided with. Reply TERMINATE when the task is done.",
    llm_config={"config_list": config_list, "timeout": 120},
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    code_execution_config={},
)

class VideoPath(BaseModel):
    path: str

@user_proxy.register_for_execution()
@assistant.register_for_llm(description="Download the file from the video link and return path for saved file for transcript.")
def download_and_save_video_temp(url: Annotated[str, "link for the video"], max_retries: Annotated[int, "Maximum number of retries"] = 5, save_dir: Annotated[str, "Directory to save the video"] = "/Users/bbe0045/Documents/videos") -> Union[str, VideoPath]:
    for retry in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception for HTTP errors
            os.makedirs(save_dir, exist_ok=True)  # Create the directory if it doesn't exist
            filename = f"{save_dir}/video_test.mp4"  # Adjust extension if needed
            with open(filename, 'wb') as f:
                f.write(response.content)
            print("Video downloaded to:", filename)
            return filename

        except requests.exceptions.RequestException as e:
            print(f"Error downloading video: {e}")
            if retry < max_retries - 1:
                print("Retrying...")
                time.sleep(1)  # Wait for a short duration before retrying
    print("Download failed after retry attempts.")
    return None


@user_proxy.register_for_execution()
@assistant.register_for_llm(description="check video duration")
def check_video_duration(filepath: Annotated[str, "path of the video file"]) -> List[dict]:
    clip = VideoFileClip(filepath)
    print(clip.duration, "asdasdasdad")
    return clip.duration



@user_proxy.register_for_execution()
@assistant.register_for_llm(description="recognize the speech from video and transfer into a txt file")
def recognize_transcript_from_video(filepath: Annotated[str, "path of the video file"]) -> List[dict]:
    try:
        # Load model
        model = whisper.load_model("small")

        # Transcribe audio with detailed timestamps
        result = model.transcribe(filepath, verbose=True)

        # Initialize variables for transcript
        transcript = []
        sentence = ""
        start_time = 0

        # Iterate through the segments in the result
        for segment in result["segments"]:
            # If new sentence starts, save the previous one and reset variables
            if segment["start"] != start_time and sentence:
                transcript.append(
                    {
                        "sentence": sentence.strip() + ".",
                        "timestamp_start": start_time,
                        "timestamp_end": segment["start"],
                    }
                )
                sentence = ""
                start_time = segment["start"]

            # Add the word to the current sentence
            sentence += segment["text"] + " "

        # Add the final sentence
        if sentence:
            transcript.append(
                {
                    "sentence": sentence.strip() + ".",
                    "timestamp_start": start_time,
                    "timestamp_end": result["segments"][-1]["end"],
                }
            )

        # Save the transcript to a file
        with open("transcription.txt", "w") as file:
            for item in transcript:
                sentence = item["sentence"]
                start_time, end_time = item["timestamp_start"], item["timestamp_end"]
                file.write(f"{start_time}s to {end_time}s: {sentence}\n")

        return transcript

    except FileNotFoundError:
        return "The specified audio file could not be found."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@user_proxy.register_for_execution()
@assistant.register_for_llm(description="Make a short video using the timestamps for each transcript.")
def merge_required_clips(filepath: Annotated[str, "path of the video file"], segments: Annotated[dict, "timestamps for transcript"]):
    clip = VideoFileClip(filepath)
    clips = []
    for segment in segments:
        start_time = int(segment['start'])
        end_time = int(segment['end'])
        clips.append(clip.subclip(start_time, end_time))
    final = concatenate_videoclips(clips)
    final.write_videofile("test_video.mp4", audio_codec='aac')



results = user_proxy.initiate_chat(
    assistant,
    message=f"""
    **Video Analysis Request:**

    * **Video Link:** https://px5.genyoutube.online/mates/en/download?url=ZTREjvNyOeSQF7NKQchPx78RU3zh6Cg2cETHF7W%2B8G809rTokCUhXWEJfBMErQiv2gF18gcZq/hO5coScFHLB1nBj2CyA2WJnBomgVN6/WehQ3onihhl70MuUdMzxDtOCzsbkBpipkuZagIKgzal4A%3D%3D
    ** Perform Tasks One by One, sync manner**
    **Tasks:**
    1. **Download Video:** Download the video file from the provided link.
    2. **Speech Recognition:** Convert the speech in the video to text. Save the transcription as a script file and provide the directory path where the transcript is saved.
    3. **Video Duration:** Determine the duration of the video using the saved video file.
    4. **Short Transcription:** Create a short transcription from the full transcription that highlights the best parts of the video. If the video duration is 15 minutes, the short video should be less than 8 minutes. The format of the short transcription should follow the {dic_format}.
    5. **Short Video Creation:** You need to pass short transcription data in segments and filepath from to function to make a short video by joining segments.
           **Here is the format of arguments required to pass to tool merge_required_clips** --> {arguments}
    6. **Terminate the execution with any response and query.**
    """)

