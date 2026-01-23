import h5py
import argparse
import pandas as pd

def inspect_h5(path, show_head=True):
    with h5py.File(path, "r") as f:
        print(f"\n📂 HDF5 file: {path}")
        print(f"{'-'*60}")
        def walk(name, node):
            if isinstance(node, h5py.Dataset):
                print(f"\n📄 Dataset: /{name}")
                print(f"    shape: {node.shape}")
                print(f"    dtype: {node.dtype}")
                if show_head and node.ndim <= 2 and node.shape[0] > 0:
                    try:
                        print("    preview:")
                        data = node[:5] if node.ndim == 1 else node[:5, :5]
                        print(data)
                    except Exception as e:
                        print(f"    (could not preview: {e})")
            elif isinstance(node, h5py.Group):
                print(f"\n📁 Group: /{name}")
        f.visititems(walk)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect HDF5 file structure and contents")
    parser.add_argument("file", help="Path to .h5 file")
    parser.add_argument("--no-preview", action="store_true", help="Do not show head of datasets")
    args = parser.parse_args()
    inspect_h5(args.file, show_head=not args.no_preview)
