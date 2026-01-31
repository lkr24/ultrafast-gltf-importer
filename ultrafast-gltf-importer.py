"""
Ultra-Fast GLTF Importer (Texture Support)
Strategy: Pre-process all GLTF files, resolve texture paths,
then bulk-create Blender objects with materials.
"""

import bpy
import json
import struct
import os
import pickle
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
import time

# ============================================
# CONFIGURATION
# ============================================

# 1. PATH TO YOUR GLTF FILES
GLTF_FOLDER = r"C:\Users\...\project-name\modelLib"

# 2. PATH TO YOUR TEXTURES
TEXTURE_FOLDER = r"C:\Users\...\project-name\modelLib\texture"

# 3. CACHE LOCATIONS (Delete these files to force a rebuild!)
CACHE_FILE = r"C:\Users\...\project-name\cache\gltf_cache.pkl"
PROGRESS_FILE = r"C:\Users\...\project-name\progress\import_progress.json"

# Import options
CREATE_COLLECTIONS = True
IMPORT_TEXTURES = True  

# ============================================
# STEP 1: PREPROCESS (Builds the Cache)
# ============================================

def preprocess_gltf_file(gltf_path):
    gltf_path = Path(gltf_path)
    tex_folder = Path(TEXTURE_FOLDER)
    
    try:
        with open(gltf_path, 'r') as f:
            gltf_data = json.load(f)
        
        # Load binary data (.bin)
        bin_data = None
        if 'buffers' in gltf_data:
            for buffer in gltf_data['buffers']:
                if 'uri' in buffer:
                    # Usually .bin is next to .gltf
                    bin_path = gltf_path.parent / buffer['uri']
                    if bin_path.exists():
                        with open(bin_path, 'rb') as f:
                            bin_data = f.read()
                        break
        
        if not bin_data:
            return None
        
        mesh_cache = {
            'name': gltf_path.stem,
            'meshes': []
        }
        
        # --- 1. Get Node Transforms ---
        node_transforms = {}
        if 'nodes' in gltf_data:
            for node in gltf_data['nodes']:
                if 'mesh' in node:
                    mesh_idx = node['mesh']
                    transform = {}
                    if 'matrix' in node: transform['matrix'] = node['matrix']
                    if 'translation' in node: transform['translation'] = node['translation']
                    if 'rotation' in node: transform['rotation'] = node['rotation']
                    if 'scale' in node: transform['scale'] = node['scale']
                    node_transforms[mesh_idx] = transform

        if 'meshes' not in gltf_data: return None

        # --- 2. Process Meshes ---
        for mesh_idx, mesh in enumerate(gltf_data['meshes']):
            for primitive in mesh['primitives']:
                if 'POSITION' not in primitive['attributes']: continue
                
                # A. Extract Positions
                pos_acc = gltf_data['accessors'][primitive['attributes']['POSITION']]
                pos_view = gltf_data['bufferViews'][pos_acc['bufferView']]
                pos_offset = pos_view.get('byteOffset', 0) + pos_acc.get('byteOffset', 0)
                stride = pos_view.get('byteStride', 12)
                count = pos_acc['count']
                
                positions = []
                for i in range(count):
                    off = pos_offset + (i * stride)
                    x, y, z = struct.unpack('<fff', bin_data[off:off+12])
                    positions.append((x, y, z))

                # B. Extract UVs (TEXCOORD_0)
                uvs = []
                if 'TEXCOORD_0' in primitive['attributes']:
                    uv_acc = gltf_data['accessors'][primitive['attributes']['TEXCOORD_0']]
                    uv_view = gltf_data['bufferViews'][uv_acc['bufferView']]
                    uv_offset_base = uv_view.get('byteOffset', 0) + uv_acc.get('byteOffset', 0)
                    uv_stride = uv_view.get('byteStride', 8)
                    
                    for i in range(count):
                        off = uv_offset_base + (i * uv_stride)
                        u, v = struct.unpack('<ff', bin_data[off:off+8])
                        uvs.append((u, v))

                # C. Extract Indices (Faces)
                indices = []
                if 'indices' in primitive:
                    idx_acc = gltf_data['accessors'][primitive['indices']]
                    idx_view = gltf_data['bufferViews'][idx_acc['bufferView']]
                    idx_offset = idx_view.get('byteOffset', 0) + idx_acc.get('byteOffset', 0)
                    idx_count = idx_acc['count']
                    ctype = idx_acc['componentType']
                    
                    if ctype == 5123: # USHORT
                        for i in range(idx_count):
                            off = idx_offset + (i * 2)
                            indices.append(struct.unpack('<H', bin_data[off:off+2])[0])
                    elif ctype == 5125: # UINT
                        for i in range(idx_count):
                            off = idx_offset + (i * 4)
                            indices.append(struct.unpack('<I', bin_data[off:off+4])[0])

                faces = []
                if indices:
                    for i in range(0, len(indices), 3):
                        faces.append((indices[i], indices[i+1], indices[i+2]))
                else:
                    for i in range(0, len(positions), 3):
                        faces.append((i, i+1, i+2))

                # D. Find Texture Path
                texture_path = None
                if 'material' in primitive:
                    mat_idx = primitive['material']
                    materials = gltf_data.get('materials', [])
                    if mat_idx < len(materials):
                        mat = materials[mat_idx]
                        pbr = mat.get('pbrMetallicRoughness', {})
                        if 'baseColorTexture' in pbr:
                            tex_idx = pbr['baseColorTexture']['index']
                            textures = gltf_data.get('textures', [])
                            if tex_idx < len(textures):
                                img_idx = textures[tex_idx]['source']
                                images = gltf_data.get('images', [])
                                if img_idx < len(images):
                                    uri = images[img_idx]['uri']
                                    
                                    # LOGIC: Check where the file actually exists
                                    
                                    # 1. Check same folder as GLTF
                                    check_local = gltf_path.parent / uri
                                    
                                    # 2. Check the specific texture folder
                                    check_tex_folder = tex_folder / uri
                                    
                                    # 3. Check just the filename in texture folder (ignore subpaths in URI)
                                    filename = Path(uri).name
                                    check_flat = tex_folder / filename
                                    
                                    if check_tex_folder.exists():
                                        texture_path = str(check_tex_folder)
                                    elif check_flat.exists():
                                        texture_path = str(check_flat)
                                    elif check_local.exists():
                                        texture_path = str(check_local)

                mesh_cache['meshes'].append({
                    'verts': positions,
                    'faces': faces,
                    'uvs': uvs,
                    'texture_path': texture_path,
                    'transform': node_transforms.get(mesh_idx, {})
                })
        
        return mesh_cache
        
    except Exception as e:
        print(f"Error preprocessing {gltf_path.name}: {e}")
        return None

def build_cache(gltf_folder, cache_file):
    print("Building cache (including texture lookup)...")
    start_time = time.time()
    
    gltf_files = sorted([str(f) for f in Path(gltf_folder).glob("*.gltf")])
    cache_data = []
    
    for i, filepath in enumerate(gltf_files):
        if (i + 1) % 100 == 0: print(f"Preprocessing: {i+1}/{len(gltf_files)}")
        data = preprocess_gltf_file(filepath)
        if data: cache_data.append(data)
    
    # Save
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, 'wb') as f:
        pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    print(f"Cache built in {time.time() - start_time:.2f}s")
    print(f"Saved to: {cache_file}")

# ============================================
# STEP 2: IMPORT
# ============================================

def get_or_create_material(texture_path, materials_cache):
    if not texture_path: return None
    
    # Avoid reloading same texture twice
    if texture_path in materials_cache:
        return materials_cache[texture_path]
    
    try:
        filename = os.path.basename(texture_path)
        mat_name = f"Mat_{filename}"
        
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        
        # Nodes
        output = nodes.new('ShaderNodeOutputMaterial')
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Specular IOR Level'].default_value = 0.5
        
        tex_node = nodes.new('ShaderNodeTexImage')
        
        # Load Image
        img = bpy.data.images.get(filename)
        if not img:
            img = bpy.data.images.load(texture_path)
        tex_node.image = img
        
        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
        
        materials_cache[texture_path] = mat
        return mat
    except Exception as e:
        print(f"Failed to create material for {texture_path}: {e}")
        return None

def parse_transform(t):
    # Convert GLTF transform to Blender Matrix
    if 'matrix' in t:
        m = t['matrix']
        # Transpose because GLTF is column-major
        return Matrix([m[0:4], m[4:8], m[8:12], m[12:16]]).transposed()
    
    mat = Matrix.Identity(4)
    if 'translation' in t:
        mat = Matrix.Translation(Vector(t['translation'])) @ mat
    if 'rotation' in t:
        q = t['rotation']
        # Blender Quaternion is (w, x, y, z), GLTF is (x, y, z, w)
        mat = Quaternion((q[3], q[0], q[1], q[2])).to_matrix().to_4x4() @ mat
    if 'scale' in t:
        s = t['scale']
        scale = Matrix.Identity(4)
        scale[0][0], scale[1][1], scale[2][2] = s[0], s[1], s[2]
        mat = scale @ mat
    return mat

def bulk_import(cache_file):
    print("Loading objects into Blender...")
    if not os.path.exists(cache_file):
        print("Cache not found! Building now...")
        build_cache(GLTF_FOLDER, CACHE_FILE)
        
    with open(cache_file, 'rb') as f:
        cache_data = pickle.load(f)
    
    materials_cache = {}
    
    start = time.time()
    
    for i, item in enumerate(cache_data):
        # Create Collection
        col_name = item['name']
        if col_name not in bpy.data.collections:
            col = bpy.data.collections.new(col_name)
            bpy.context.scene.collection.children.link(col)
        else:
            col = bpy.data.collections[col_name]
            
        for m_idx, mesh_info in enumerate(item['meshes']):
            # Create Mesh
            mesh_name = f"{item['name']}_{m_idx}"
            bm = bpy.data.meshes.new(mesh_name)
            
            verts = [Vector(v) for v in mesh_info['verts']]
            bm.from_pydata(verts, [], mesh_info['faces'])
            
            # Apply UVs (Fastest method)
            if mesh_info['uvs']:
                uv_layer = bm.uv_layers.new(name="UVMap")
                uvs = mesh_info['uvs']
                # Map loops to vertex indices
                for poly in bm.polygons:
                    for loop_index in poly.loop_indices:
                        vert_index = bm.loops[loop_index].vertex_index
                        u, v = uvs[vert_index]
                        # Flip V for Blender
                        uv_layer.data[loop_index].uv = (u, 1.0 - v)
            
            bm.update()
            
            # Create Object
            obj = bpy.data.objects.new(mesh_name, bm)
            
            # Apply Material
            if IMPORT_TEXTURES and mesh_info['texture_path']:
                mat = get_or_create_material(mesh_info['texture_path'], materials_cache)
                if mat:
                    obj.data.materials.append(mat)
            
            # Apply Transform
            if mesh_info['transform']:
                obj.matrix_world = parse_transform(mesh_info['transform'])
                
            col.objects.link(obj)
            
        if (i+1) % 50 == 0:
            print(f"Imported {i+1} objects...")

    print(f"Finished in {time.time() - start:.2f}s")

if __name__ == "__main__":
    # Force rebuild cache if it doesn't exist
    if not os.path.exists(CACHE_FILE):
        build_cache(GLTF_FOLDER, CACHE_FILE)
    else:
        # Ask user (in console) or just run
        # Ideally, delete the .pkl file manually if you changed texture folders
        pass
        
    bulk_import(CACHE_FILE)
