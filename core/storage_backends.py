"""
Custom Amazon S3 storage backends for Django.

Separates static asset delivery from media file uploads and enforces
server-side encryption and secure presigned URLs on private attachments.
"""

from storages.backends.s3boto3 import S3Boto3Storage


class StaticStorage(S3Boto3Storage):
    """
    Storage backend for static files (CSS, JS, images) stored in Amazon S3.
    Files are publicly readable with cache headers.
    """
    location = 'static'
    default_acl = None
    file_overwrite = True
    querystring_auth = False


class MediaStorage(S3Boto3Storage):
    """
    Storage backend for user uploads and task attachments stored in Amazon S3.
    Uses presigned URLs for secure access and avoids overwriting existing files.
    """
    location = 'media'
    default_acl = None
    file_overwrite = False
    querystring_auth = True
