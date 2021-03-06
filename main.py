# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

# Press the green button in the gutter to run the script.
import os
from colorama import init
import subprocess as sp
import psutil
import argparse
from colorama import Fore, Back, Style
init()

parser = argparse.ArgumentParser(description='Process lots of NIF files at once.')
parser.add_argument('InFolder',
                       metavar='infolder',
                       type=str,
                       help='the directory containing the input structure ("textures" and "meshes" folders)')

parser.add_argument('OutFolder',
                       metavar='outfolder',
                       type=str,
                       help='the directory containing the output structure ("textures" and "meshes" folders)')

parser.add_argument('MaxProcesses',
                       metavar='maxproc',
                       type=int,
                       help='the maximum number of processes allowed to be running at a time')

args = parser.parse_args()
print(args)

DETACHED_PROCESS = 0x00000008

MAX_MESH_JOBS = args.MaxProcesses
MAX_TEXTURE_JOBS = args.MaxProcesses * 2


def execute():
    print(Fore.LIGHTGREEN_EX +
          "Welcome to DekuTree's NIF to GLTF batch conversion utility.")
    print("Please wait while NIF files are converted!")

    mesh_process_count = 0
    texture_process_count = 0
    mesh_pids = []
    texture_pids = []

    in_folder = args.InFolder
    out_folder = args.OutFolder

    # debug
    mesh_root = os.path.join(in_folder, "meshes")
    #mesh_root = os.path.join(in_folder, "meshes", "architecture", "whiterun", "wrbuildings")
    #mesh_root = os.path.join(in_folder, "meshes")

    #mesh_root = os.path.join(in_folder, "meshes")
    texture_root = os.path.join(in_folder)

    print(Fore.YELLOW + "Scanning directories for DDS files!")
    current_dds_count = 0
    max_dds_files = 0
    for dirpath, dirs, files in os.walk(mesh_root):
        for file in files:
            if "actors" not in dirpath and "animobjects" not in dirpath:
                if ".nif" in file:
                    max_dds_files += 1
    print("Done: Found " + str(max_dds_files) + " DDS files!")

    print(Fore.YELLOW + "Scanning directories for NIF files!")
    current_nif_count = 0
    max_nif_files = 0
    for dirpath, dirs, files in os.walk(mesh_root):
        for file in files:
            if "actors" not in dirpath and "animobjects" not in dirpath:
                if ".nif" in file:
                    max_nif_files += 1
    print("Done: Found " + str(max_nif_files) + " NIF files!")

    print("Converting textures")
    for dirpath, dirs, files in os.walk(os.path.join(texture_root, "textures")):
        for file in files:
            if "actors" not in dirpath and "animobjects" not in dirpath:
                if ".dds" in file:
                    startupinfo = sp.STARTUPINFO()
                    startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                    output_path = os.path.join(out_folder, os.path.relpath(
                        os.path.join(dirpath, file).replace(".dds", ".png"), in_folder))

                    if not os.path.isfile(output_path):
                        # generate output folder structure
                        if not os.path.exists(os.path.dirname(output_path)):
                            os.makedirs(os.path.dirname(output_path))

                        vips = sp.Popen(['vips/vips.exe', "affine", os.path.join(
                            dirpath, file), output_path, ' 1 0 0 1'], startupinfo=startupinfo).pid

                        texture_process_count += 1
                        current_dds_count += 1
                        print(Fore.BLUE + "PID: [" + str(vips) + "] Starting job for " + str(file) + " - " + str(
                            current_dds_count) + " out of " + str(max_dds_files) + " DDS files.")
                        texture_pids.append([vips, file, current_dds_count])

                        if texture_process_count > MAX_TEXTURE_JOBS:
                            print(
                                Fore.YELLOW + "Reached max job count, waiting for some to finish before starting more.")
                            while len(texture_pids) > 0:
                                for p, f, i in texture_pids:
                                    if not psutil.pid_exists(p):
                                        print(Fore.GREEN + "PID: [" + str(p) + "] Finished job for " + str(
                                            f) + " - " + str(i) + " out of " + str(max_dds_files) + " DDS files.")
                                        texture_pids.remove([p, f, i])
                                        texture_process_count -= 1

    for dirpath, dirs, files in os.walk(mesh_root):
        for file in files:
            if "actors" not in dirpath and "animobjects" not in dirpath:
                os_path = file
                split = (os_path.split(os.sep))[-5:]
                rejoin = os.path.join(*split).replace(os.sep, "/")

                # import all root blocks
                pid = sp.Popen(["venv/scripts/pythonw", "file_process.py", os.path.join(
                    dirpath, file), texture_root, in_folder, out_folder], creationflags=DETACHED_PROCESS).pid
                #pid = sp.Popen(["C:/Program Files/Blender Foundation/Blender 2.91/blender.exe", "--background", "--python", "file_process.py", os.path.join(
                #    dirpath, file), texture_root, in_folder, out_folder], creationflags=DETACHED_PROCESS).pid
                mesh_process_count += 1
                current_nif_count += 1
                print(Fore.BLUE + "PID: [" + str(pid) + "] Starting job for " + str(file) + " - " + str(
                    current_nif_count) + " out of " + str(max_nif_files) + " NIF files.")
                mesh_pids.append([pid, file, current_nif_count])

                if mesh_process_count > MAX_MESH_JOBS:
                    print(
                        Fore.YELLOW + "Reached max job count, waiting for some to finish before starting more.")
                    while len(mesh_pids) > 0:
                        for p, f, i in mesh_pids:
                            if not psutil.pid_exists(p):
                                print(Fore.GREEN + "PID: [" + str(p) + "] Finished job for " + str(
                                    f) + " - " + str(i) + " out of " + str(max_dds_files) + " NIF files.")
                                mesh_pids.remove([p, f, i])
                                mesh_process_count -= 1
        try:
            print("")
        except Exception as err:
            print(
                "Warning: read failed due corrupt file,"
                " corrupt format description, or bug. Error: " + str(err))


execute()
