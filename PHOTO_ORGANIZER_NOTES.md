# Photo Organizer — Quick Reference

Script: ~/AUBIEETERNAL/organize_photos.py
Uses: InsightFace buffalo_l + ~/aubie_storage/faces/faces.npz (matthew:37, gabriela:6)

## Dry run
python3 ~/AUBIEETERNAL/organize_photos.py \
  --source /home/aubieeternal \
  --output ~/photos_sorted \
  --dry-run

## Real run (copies, originals untouched)
python3 ~/AUBIEETERNAL/organize_photos.py \
  --source /home/aubieeternal \
  --output ~/photos_sorted \
  --copy

## After sorting — enroll best Matthew shots
python3 ~/AUBIEETERNAL/organize_photos.py \
  --enroll-best --source ~/photos_sorted/matthew --name matthew
sudo systemctl restart aubieeternal-assistant

## Fix if numpy error on faces.npz
# np.load needs allow_pickle=True — already applied in script

## Transfer iPhone photos from Windows
# powershell: scp -r $env:USERPROFILE\Downloads\iPhone_Photos aubieeternal@100.105.81.27:~/Pictures/
