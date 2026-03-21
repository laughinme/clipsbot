from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


ALLOWED_AVATAR_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}


def _default_extension(content_type: str) -> str:
    if content_type == "image/jpeg":
        return ".jpg"
    if content_type == "image/png":
        return ".png"
    if content_type == "image/webp":
        return ".webp"
    return ".bin"


@dataclass(slots=True)
class StorageObjectStat:
    size_bytes: int
    content_type: str | None


class MediaStorageService:
    def __init__(
        self,
        *,
        internal_endpoint: str,
        public_endpoint: str,
        region: str,
        access_key: str,
        secret_key: str,
        use_path_style: bool,
        presign_expires_sec: int,
        public_bucket: str,
        private_bucket: str,
    ) -> None:
        self.public_endpoint = public_endpoint.rstrip("/")
        self.region = region
        self.presign_expires_sec = presign_expires_sec
        self.public_bucket = public_bucket
        self.private_bucket = private_bucket

        s3_config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if use_path_style else "auto"},
        )

        self._internal_client = boto3.client(
            "s3",
            endpoint_url=internal_endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,
        )
        self._presign_client = boto3.client(
            "s3",
            endpoint_url=public_endpoint,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=s3_config,
        )

    def build_avatar_key(self, user_id: UUID | str, filename: str, content_type: str) -> str:
        ext = Path(filename).suffix.lower()
        allowed_ext = _EXTENSIONS_BY_CONTENT_TYPE.get(content_type, set())
        if ext not in allowed_ext:
            ext = _default_extension(content_type)
        return f"avatars/{user_id}/{uuid4().hex}{ext}"

    def create_presigned_upload_url(
        self,
        *,
        bucket: str,
        key: str,
        content_type: str,
        expires_in: int | None = None,
    ) -> str:
        return self._presign_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in or self.presign_expires_sec,
            HttpMethod="PUT",
        )

    def create_presigned_download_url(
        self,
        *,
        bucket: str,
        key: str,
        expires_in: int | None = None,
    ) -> str:
        return self._presign_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in or self.presign_expires_sec,
        )

    def build_public_url(self, *, bucket: str, key: str) -> str:
        encoded_key = quote(key, safe="/")
        return f"{self.public_endpoint}/{bucket}/{encoded_key}"

    def get_object_stat(self, *, bucket: str, key: str) -> StorageObjectStat | None:
        try:
            response = self._internal_client.head_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

        return StorageObjectStat(
            size_bytes=int(response.get("ContentLength", 0)),
            content_type=response.get("ContentType"),
        )

    def delete_object(self, *, bucket: str, key: str) -> None:
        self._internal_client.delete_object(Bucket=bucket, Key=key)

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self._internal_client.head_bucket(Bucket=bucket)
            return
        except ClientError:
            pass

        kwargs: dict[str, object] = {"Bucket": bucket}
        if self.region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": self.region,
            }
        self._internal_client.create_bucket(**kwargs)

    def ensure_buckets(self) -> None:
        self.ensure_bucket(self.public_bucket)
        self.ensure_bucket(self.private_bucket)

    def check_health(self) -> None:
        """Raise an exception if storage is unreachable or buckets are missing."""
        self._internal_client.list_buckets()
        self._internal_client.head_bucket(Bucket=self.public_bucket)
        self._internal_client.head_bucket(Bucket=self.private_bucket)

    def put_object_bytes(
        self,
        *,
        bucket: str,
        key: str,
        payload: bytes,
        content_type: str,
    ) -> None:
        self._internal_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )

    def delete_prefix(self, *, bucket: str, prefix: str) -> int:
        deleted_count = 0
        paginator = self._internal_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            contents = page.get("Contents", [])
            if not contents:
                continue

            objects = [{"Key": item["Key"]} for item in contents if "Key" in item]
            if not objects:
                continue

            self._internal_client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": objects, "Quiet": True},
            )
            deleted_count += len(objects)

        return deleted_count
