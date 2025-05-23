import os

def print_tree(root, max_depth, indent='', current_depth=0):
    if current_depth > max_depth:
        return
    entries = sorted(os.listdir(root))
    for i, name in enumerate(entries):
        path = os.path.join(root, name)
        is_last = (i == len(entries)-1)
        pointer = '└─ ' if is_last else '├─ '
        print(indent + pointer + name + ('/' if os.path.isdir(path) else ''))
        if os.path.isdir(path):
            extension = '   ' if is_last else '│  '
            print_tree(path, max_depth, indent + extension, current_depth+1)

if __name__ == '__main__':
    base = r"D:\PROJECT\translate_for_livestream"   # ganti kalau perlu
    # max_depth=0 -> hanya list root; max_depth=1 -> root + satu level subfolder
    print_tree(base, max_depth=1)
