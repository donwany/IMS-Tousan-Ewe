import os
from pydub import AudioSegment

# Specify the directory containing the .mp3 files
input_directory = '/home/ts75080/Documents/tts-demo/tts_train_ewe/LJSpeech-1.1/wavs/'
output_directory = '/home/ts75080/Documents/tts-demo/tts_train_ewe/LJSpeech-1.1/train/wavs/'

# Create the output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

# Loop over all files in the directory
for filename in os.listdir(input_directory):
    if filename.endswith('.mp3'):
        # Construct full file path
        input_path = os.path.join(input_directory, filename)
        output_path = os.path.join(output_directory, f"{os.path.splitext(filename)[0]}.wavs")

        # Convert the .mp3 file to .wavs
        try:
            audio = AudioSegment.from_mp3(input_path)
            audio.export(output_path, format='wavs')
            print(f"Converted {filename} to {output_path}")
        except Exception as e:
            print(f"Error converting {filename}: {e}")

print("Conversion of all .mp3 files to .wavs completed!")