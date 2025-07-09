import os
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import re

input_yaml = "./recipes/ashs/build.yaml"
output_jinja = "ashs.j2"

# 0.Read original yaml to generate jinja file
with open(input_yaml, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    line = re.sub(r'base-image:\s*[^\s]+', 'base-image: {{ base_image }}', line)
    new_lines.append(line)

with open(output_jinja, 'w') as f:
    f.writelines(new_lines)

#get the tag from the original yaml
tag = None
for line in lines:
    match = re.match(r'version:\s*([\d\.]+)', line)
    if match:
        tag = match.group(1)
        break

if tag is None:
    raise ValueError("Could not find version tag in the YAML file.")

# 1. Setup Jinja2 environment
env = Environment(loader=FileSystemLoader('.'))
template_file = 'ashs.j2'
image_name = os.path.splitext(template_file)[0]  # "ashs"
template = env.get_template(template_file)

# 2. Define base-images
base_images = ["ubuntu:16.04", "ubuntu:18.04", "ubuntu:20.04", "ubuntu:24.04"]
#base_images = ["ubuntu:16.04"]


config_meta = []

# 3. Render config files per base image
for base_image in base_images:
    file_name = f'config_{image_name}_{tag}.yaml'

    output = template.render(base_image=base_image)

    with open(file_name, 'w') as f:
        f.write(output)

    print(f"Generated {file_name}")
    config_meta.append({
        "file": file_name,
        "image_name": image_name,
        "base_image": base_image,
        "tag": tag
    })

# 4. Build and validate images
passed_recipes = []
failed_recipes = []

for meta in config_meta:
    file = meta["file"]
    image_name = meta["image_name"]
    tag = meta["tag"]
    recipe_name = f"{image_name}:{tag}"
    recipe_name_config = f"{image_name}:{tag}:{base_image}"

    print(f"\nTesting config file: {file}")
    cmd = ["./build.py", "--recreate", "--build", file, "build"]
    result = subprocess.run(cmd, capture_output=True, text=True)

    output = result.stdout + result.stderr
    log_file = f"log_{image_name}_{tag}.txt"
    with open(log_file, 'w') as f:
        f.write(output)

    expected_msg = "Docker image built successfully"

    if expected_msg in output:
        print(f"[{recipe_name_config}] Build succeeded")
        passed_recipes.append(recipe_name_config)
        remove_cmd = ["docker", "rmi", f"{recipe_name}"]
        subprocess.run(remove_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        print(f"[{recipe_name_config}] Build failed or unexpected output")
        failed_recipes.append(recipe_name_config)

# 5. Build summary
print("\nBuild Summary:")
print("--------------------------")

if passed_recipes:
    print("Passed:")
    for name in passed_recipes:
        print(f"  - {name}")

if failed_recipes:
    print("\nFailed:")
    for name in failed_recipes:
        print(f"  - {name} (see log_{name.replace(':', '_')}.txt)")

# 6. Optional cleanup of generated file
cleanup = False
if cleanup:
    print("\nCleaning up generated files...")
    for meta in config_meta:
        config_file = meta["file"]
        log_file = f"log_{meta['image_name']}_{meta['tag']}.txt"

        for path in [config_file, log_file]:
            try:
                os.remove(path)
                print(f"Deleted: {path}")
            except Exception as e:
                print(f"Failed to delete {path}: {e}")

# 7. Exit code
if failed_recipes:
    exit(1)
else:
    print("\nAll recipes built successfully.")
