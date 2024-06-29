# import os
# import json
#
#
# def build_path_to_transcript_dict_ewe(re_cache=False):
#     root = "/home/ts75080/Documents/IMS-Toucan/EweData"
#     cache_path = os.path.join(root, "pttd_cache.json")  # Change the extension to .json
#
#     if not os.path.exists(cache_path) or re_cache:
#         path_to_transcript = dict()
#
#         metadata_path = os.path.join(root, "metadata.csv")
#         if not os.path.exists(metadata_path):
#             print(f"Error: The file {metadata_path} does not exist.")
#             return path_to_transcript
#
#         with open(metadata_path, "r", encoding="utf8") as file:
#             lookup = file.read()
#
#         if not lookup.strip():
#             print(f"Error: The file {metadata_path} is empty.")
#             return path_to_transcript
#
#         for line in lookup.split("\n"):
#             if line.strip() != "":
#                 parts = line.split("|")
#                 if len(parts) >= 2:
#                     norm_transcript = parts[1]
#                     wav_path = os.path.join(root, parts[0] + ".mp3")
#
#                     if os.path.exists(wav_path):
#                         path_to_transcript[wav_path] = norm_transcript
#                     else:
#                         print(f"Warning: The file {wav_path} does not exist.")
#                 else:
#                     print(f"Warning: The line '{line}' is not in the expected format.")
#
#         print(f"Collected {len(path_to_transcript)} entries.")
#
#         # Save to JSON file
#         with open(cache_path, "w", encoding="utf8") as json_file:
#             json.dump(path_to_transcript, json_file, ensure_ascii=False, indent=4)
#
#         return path_to_transcript
#
#     else:
#         # Load from JSON file
#         with open(cache_path, "r", encoding="utf8") as json_file:
#             return json.load(json_file)
#
#
# if __name__ == '__main__':
#     path_to_transcript = build_path_to_transcript_dict_ewe()
#     print("Final dictionary:", path_to_transcript)

import os
import json


def build_path_to_transcript_dict_ewe(re_cache=False):
    root = "/home/ts75080/Documents/IMS-Toucan/EweData"
    cache_path = os.path.join(root, "pttd_cache.json")  # Change the extension to .json

    if not os.path.exists(cache_path) or re_cache:
        path_to_transcript = {}

        with open(os.path.join(root, "metadata.csv"), "r", encoding="utf8") as file:
            lookup = file.read()

        for line in lookup.split("\n"):
            if line.strip() != "":
                parts = line.split("|")
                if len(parts) >= 2:
                    norm_transcript = parts[1]
                    wav_path = os.path.join(root, parts[0] + ".mp3")
                    if os.path.exists(wav_path):
                        path_to_transcript[wav_path] = norm_transcript

        # Save to JSON file
        with open(cache_path, "w", encoding="utf8") as json_file:
            json.dump(path_to_transcript, json_file, ensure_ascii=False, indent=4)

        return path_to_transcript

    else:
        # Load from JSON file
        with open(cache_path, "r", encoding="utf8") as json_file:
            return json.load(json_file)


if __name__ == '__main__':
    print(build_path_to_transcript_dict_ewe())

# import os
#
#
# def build_path_to_transcript_dict_ewe(re_cache=False):
#     root = "/home/ts75080/Documents/IMS-Toucan/EweData"
#     cache_path = os.path.join(root, "pttd_cache.pt")
#     if not os.path.exists(cache_path) or re_cache:
#         path_to_transcript = dict()
#         with open(os.path.join(root, "metadata.csv"), "r", encoding="utf8") as file:
#             lookup = file.read()
#         for line in lookup.split("\n"):
#             if line.strip() != "":
#                 norm_transcript = line.split("|")[1]
#                 wav_path = os.path.join(root, "wav", line.split("|")[0] + ".mp3")
#                 if os.path.exists(wav_path):
#                     path_to_transcript[wav_path] = norm_transcript
#                     # print(path_to_transcript)
#         # torch.save(path_to_transcript, cache_path)
#         return path_to_transcript
#     # return torch.load(cache_path)
#
#
# if __name__ == '__main__':
#     print(build_path_to_transcript_dict_ewe())

