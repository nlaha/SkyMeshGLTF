# SkyMeshGLTF
A mesh converter for TESV Skyrim designed to convert every model in the game to a GLTF file with materials and textures.

## Developer Note

SkyMeshGLTF consists of two components, a python script to convert 1 NIF file to 1 GLTF file, and a batch conversion script to convert many NIF files to many GLTF files while retaining the file folder structure, this is useful if you want to automate asset import and placement in another game engine.

Due to the limitations of GLTF files not being able to reference texture URIs that are outside the parent folder of the GLTF file, the textures will be represented as absolute paths, this means you cannot move the GLTF files once they are generated. There are various ways to fix this, one is baking texture data into the GLTF file itself, however, as skyrim reuses textures frequently, this would increase the total folder size by orders of magnitude as textures would be duplicated across GLTF files. I'm hoping to implement a solution that allows shared textures whilst removing the absolute file paths.

As this project is in the very early stages of development there are several things that could be improved:
- Don't use absolute file paths in GLTF files (without causing massive texture duplication)
- Spawn processes immediately after process count is less than max, instead of waiting until it reaches zero
- Support animations
- Support rigged models
- Support more texture maps
- Support other advanced features of NIF files

## Usage

1. install requirements.txt

        pip install -r requirements.txt

2. run file_process.py to process single files

        python file_process.py <nif filepath> <folder containing "textures" folder> <in folder> <out folder>

3. run main.py to process an entire skyrim extraction

        python main.py <in folder> <out folder> <max proceses>

For the above, <in folder> should contain the "meshes" and "textures" folder from BSA extractor
