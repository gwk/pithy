



# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

'''
`craft-mac-ions` takes an input image (1024x1024) and creates a set of icons for Mac.
'''

from argparse import ArgumentParser

from PIL import ImageDraw
from PIL.Image import Image, new as Image_new, open as Image_open, Resampling
from pithy.path import split_stem_ext


def main() -> None:
  arg_parser = ArgumentParser(description='Create mac icons.')
  arg_parser.add_argument('path', help='Path to the original 1024x1024 icon artwork.')

  args = arg_parser.parse_args()
  path = args.path

  img = Image_open(path)

  # TODO: resize for the user.
  if img.size != (1024, 1024): exit(f'{path!r} is not 1024x1024.')

  for dst_width, rounded in dst_sizes:
    round_icon(path=path, img=img, dst_width=dst_width, rounded=rounded)


def round_icon(path:str, img:Image, dst_width:int, rounded:bool) -> None:

  stem, ext = split_stem_ext(path)

  dst_size = (dst_width, dst_width)
  r = dst_width * 0.185

  assert rounded, 'non-rounded output is not yet implemented.'

  # Create a multisampled mask, since PIL drawing commands are not antialiased.
  multisamples = 8
  ms_mask_w = dst_width * multisamples
  ms_size = (ms_mask_w, ms_mask_w)

  mask_ms = Image_new('L', ms_size, 0)
  draw = ImageDraw.Draw(mask_ms)
  draw.rounded_rectangle(((0,0), ms_size), radius=r*multisamples, fill=255)

  # Downsample the image and the mask to the desired size.
  img_ds = img.resize(size=dst_size, resample=Resampling.LANCZOS)
  mask_ds = mask_ms.resize(size=dst_size, resample=Resampling.LANCZOS)

  # Mask the image by creating a new blank and using `paste` with a mask.
  dst = Image_new(mode='RGBA', size=dst_size, color=(0,0,0,0)) # Transparent black background.
  dst.paste(img_ds, box=(0,0), mask=mask_ds)

  dst.save(f'{stem}-{dst_width}{ext}')


# For now, round all corners. It may be that the app store images should not have rounded corners.
dst_sizes = {
  (1024, True),
  (512, True),
  (256, True),
  (128, True),
  (64, True),
  (32, True),
  (16, True),
}
