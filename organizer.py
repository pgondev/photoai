import os
import shutil

class FileOrganizer:
    def __init__(self, base_dest_dir):
        self.base_dest_dir = base_dest_dir

    def get_target_path(self, date_obj, is_duplicate=False):
        if is_duplicate:
            return os.path.join(self.base_dest_dir, "Duplicates")
        elif not date_obj:
            return os.path.join(self.base_dest_dir, "Unknown_Date")
        else:
            folder_name = os.path.join(str(date_obj.year), date_obj.strftime("%B"))
            return os.path.join(self.base_dest_dir, folder_name)

    def organize_file(self, file_path, date_obj, dry_run=False, is_duplicate=False):
        target_dir = self.get_target_path(date_obj, is_duplicate)

        if not dry_run:
            os.makedirs(target_dir, exist_ok=True)
            try:
                # We use move instead of copy to actually organize and clean up source.
                shutil.move(file_path, target_dir)
                return target_dir
            except Exception as e:
                print(f"  Error moving file: {e}")
                return None
        else:
            return target_dir
