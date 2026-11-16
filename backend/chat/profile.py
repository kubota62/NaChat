import io
import uuid
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile


def prepare_avatar(upload):
    if not upload or upload.size > 5 * 1024 * 1024:
        raise ValidationError('画像は5MB以下のPNG・JPEG・WebPを選んでください。')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if source.format not in ['PNG', 'JPEG', 'WEBP']:
                    raise ValidationError('PNG・JPEG・WebP形式の画像を選んでください。')
                if source.width * source.height > 20_000_000:
                    raise ValidationError('画像は2000万画素以下にしてください。')
                source.load()
                picture = ImageOps.exif_transpose(source).convert('RGB')
                picture = ImageOps.fit(picture, (256, 256), method=Image.Resampling.LANCZOS)
                output = io.BytesIO()
                picture.save(output, format='JPEG', quality=85)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError('画像を読み込めません。別の画像を選んでください。')
    return ContentFile(output.getvalue(), name=uuid.uuid4().hex + '.jpg')
