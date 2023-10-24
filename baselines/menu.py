import argparse
import os
import re
import requests
import json
import subprocess
import glob
from pathlib import Path
import uuid
from red_gym_env import RedGymEnv
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.utils import set_random_seed
from stable_baselines3.common.callbacks import CheckpointCallback

DEFAULT_BASE_URL = "http://127.0.0.1:5000"
directory_path = 'downloaded_checkpoints'
if not os.path.exists(directory_path):
    os.makedirs(directory_path)
    #print(f"Directory '{directory_path}' created.")
#else:
    #print(f"Directory '{directory_path}' already exists.")

'''
import subprocess

# Define the Git branch you want to update
git_branch = "your_branch_name"

# Define the Git command to update the branch
git_command = f"git pull origin {git_branch}"

try:
    # Run the Git command
    subprocess.run(git_command, shell=True, check=True)
    print(f"Branch {git_branch} updated successfully.")
except subprocess.CalledProcessError as e:
    print(f"Error updating branch {git_branch}: {e}")
'''


def make_env(rank, env_conf, seed=0):
    """
    Utility function for multiprocessed env.
    :param env_conf: (dict) environment configuration
    :param seed: (int) the initial seed for RNG
    :param rank: (int) index of the subprocess
    """
    def _init():
        env = RedGymEnv(env_conf)
        env.reset(seed=(seed + rank))
        return env

    set_random_seed(seed)
    return _init

def parse_args():
    parser = argparse.ArgumentParser(description='Machine Learning Checkpoint Management for RedGym Environment')
    parser.add_argument('--menu', action='store_true', help='Show the menu')
    parser.add_argument('--restore', help='Restore from a URL or use the default URL')
    parser.add_argument('--upload', help='Upload to a URL or use the default URL')
    parser.add_argument('--url', help='Specify a custom BASE_URL')
    return parser.parse_args()

def show_menu(selected_checkpoint):
    while True:  # Create an infinite loop
        session_dict, downloaded_checkpoints = list_all_sessions_and_pokes()
        if not session_dict:
            print("No checkpoints found.")
            return selected_checkpoint

        downloaded_checkpoint_count = len(session_dict)
        print(f"\nAvailable sessions sorted by their largest checkpoints:")
        for i, (session, largest_step) in enumerate(session_dict.items()):
            print(f"  {i + 1}. {session}/poke-{largest_step}_steps.zip")

        print("\nDownloaded checkpoints:")
        for i, checkpoint in enumerate(downloaded_checkpoints, start=downloaded_checkpoint_count + 1):
            print(f"  {i}. {checkpoint}")

        print("\n  95. Future-Delete Saved Files")
        print("  96. Resume from remote")
        print("  97. Upload to remote")
        print("  98. Exit")
        print("  99. Start a new run")
        menu_selection = input("Enter the number of the menu option: ")

        if menu_selection.isdigit():
            selection = int(menu_selection)
            if 1 <= selection <= len(session_dict):
                selected_session = list(session_dict.keys())[selection - 1]
                selected_step = session_dict[selected_session]
                selected_checkpoint = f"{selected_session}/poke_{selected_step}_steps.zip"
                return selected_checkpoint  # Return the selected checkpoint and exit the loop
            elif downloaded_checkpoint_count + 1 <= selection <= downloaded_checkpoint_count + len(downloaded_checkpoints):
                selected_checkpoint = os.path.join('downloaded_checkpoints', downloaded_checkpoints[selection - downloaded_checkpoint_count - 1])
                return selected_checkpoint  # Return the selected checkpoint and exit the loop
            elif menu_selection == '96':
                selected_checkpoint = remote_actions()
                if selected_checkpoint:
                    return selected_checkpoint  # Return the selected checkpoint and exit the loop
            elif menu_selection == '97':
                selection = int(input("Enter your selection for remote upload: "))
                upload(selection, session_dict)
            elif menu_selection == '98':
                print("Exiting the menu.")
                return None  # Exit the loop and return None
            elif menu_selection == '99':
                return None  # Exit the loop and return None
            else:
                print("Invalid selection.")
        else:
            print("Invalid input. Please enter a valid number.")

def list_all_sessions_and_pokes():
    all_folders = os.listdir()
    session_folders = [folder for folder in all_folders if re.match(r'session_[0-9a-fA-F]{8}', folder)]
    session_dict = {}
    downloaded_checkpoints = []

    for session_folder in session_folders:
        poke_files = glob.glob(f"{session_folder}/poke_*_steps.zip")
        if poke_files:
            largest_poke_file = max(poke_files, key=lambda x: int(re.search(r'poke_(\d+)_steps', x).group(1)))
            largest_step = int(re.search(r'poke_(\d+)_steps', largest_poke_file).group(1))
            session_dict[session_folder] = largest_step

    downloaded_checkpoints = [file for file in os.listdir('downloaded_checkpoints') if file.endswith('.zip')]
    sorted_session_dict = {k: v for k, v in sorted(session_dict.items(), key=lambda item: item[1], reverse=True)}
    return sorted_session_dict, downloaded_checkpoints

def remote_actions():
    BASE_URL = DEFAULT_BASE_URL  # Use the default URL

    response = requests.get(f"{BASE_URL}/uploads/metadata.txt")

    if response.status_code != 200:
        print("Failed to fetch metadata from the server.")
        return None

    server_metadata = response.text.strip()
    if not server_metadata:
        print("No checkpoint metadata found. Is this an empty server?")
        return None

    try:
        server_metadata = json.loads(server_metadata)
    except json.decoder.JSONDecodeError as e:
        print("Error decoding JSON:", str(e))
        return None

    print(f"\nAvailable remote checkpoints:")
    for i, entry in enumerate(server_metadata):
        print(f"{i + 1}. Filename: {entry['filename']}, Steps: {entry['steps']}")

    server_selection = input("Enter the number of the checkpoint you want to download: ")
    try:
        server_selection = int(server_selection)
        if 1 <= server_selection <= len(server_metadata):
            selected_server_entry = server_metadata[server_selection - 1]
            filename = selected_server_entry['filename']
            download_response = requests.get(f"{BASE_URL}/uploads/{filename}")

            if download_response.status_code == 200:
                with open(f"downloaded_checkpoints/{filename}", 'wb') as f:
                    f.write(download_response.content)
                print(f"Downloaded checkpoint: {filename}")
            else:
                print(f"Failed to download the selected checkpoint: {filename}")
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input. Please enter a valid number.")

    return None

def restore(url, download_selection):
    response = requests.get(url)

    if response.status_code == 200:
        filename = url.split("/")[-1]
        with open(filename, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded checkpoint: {filename}")
        return filename
    else:
        print("Failed to download checkpoint.")
        return None

def upload(selection, session_dict):
    try:
        selected_session = list(session_dict.keys())[selection - 1]
        selected_step = session_dict[selected_session]
        file_path = f"{selected_session}/poke_{selected_step}_steps.zip"

        upload_command = f"curl -X POST -F file=@{file_path} http://127.0.0.1:5000/upload"
        subprocess.run(upload_command, shell=True)
    except (ValueError, IndexError):
        print("Invalid selection")

# ... (previous code)

def main(selected_checkpoint):
    sess_path = Path(f'session_{str(uuid.uuid4())[:8]}')
    ep_length = 2048 * 10
    env_config = {
        'headless': True, 'save_final_state': True, 'early_stop': False,
        'action_freq': 24, 'init_state': '../has_pokedex_nballs.state', 'max_steps': ep_length,
        'print_rewards': True, 'save_video': False, 'fast_video': True, 'session_path': sess_path,
        'gb_path': '../PokemonRed.gb', 'debug': False, 'sim_frame_dist': 2_000_000.0,
        'use_screen_explore': True, 'reward_scale': 4, 'extra_buttons': False,
        'explore_weight': 3
    }

    print(env_config)
    num_cpu = 16
    env = SubprocVecEnv([make_env(i, env_config) for i in range(num_cpu)])
    checkpoint_callback = CheckpointCallback(save_freq=ep_length, save_path=sess_path, name_prefix='poke')
    learn_steps = 40

    print('\nLoading checkpoint', selected_checkpoint, ' ... \n')
    model = PPO.load(selected_checkpoint, env=env)
    model.n_steps = ep_length
    model.n_envs = num_cpu
    model.rollout_buffer.buffer_size = ep_length
    model.rollout_buffer.n_envs = num_cpu
    model.rollout_buffer.reset()
    for i in range(learn_steps):
        model.learn(total_timesteps=(ep_length) * num_cpu * 1000, callback=checkpoint_callback)

if __name__ == '__main__':
    selected_checkpoint = None
    selected_checkpoint = show_menu(selected_checkpoint)  # Update the selected_checkpoint
    main(selected_checkpoint)  # Pass the selected_checkpoint to main

