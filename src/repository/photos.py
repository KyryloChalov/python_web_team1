import datetime as DT
from typing import List
import uuid
import cloudinary
import cloudinary.uploader
from src.conf.config import config

from src.models.models import User, Tag
from sqlalchemy import select, update, func, extract, and_
from datetime import date, timedelta
from fastapi import File, HTTPException

# from sqlalchemy.sql.sqltypes import Date
from sqlalchemy.ext.asyncio import AsyncSession

from src.conf.messages import SOMETHING_WRONG, PHOTO_SUCCESSFULLY_ADDED
from src.models.models import Photo


async def get_or_create_tag(tag_name: str, db: AsyncSession) -> Tag:

    existing_tag = await db.execute(select(Tag).filter(Tag.name == tag_name))
    tag = existing_tag.scalar_one_or_none()

    if not tag:
        tag = Tag(name=tag_name)
        db.add(tag)
        await db.commit()
        await db.refresh(tag)

    return tag


def check_tags_quantity(tags: list[str]) -> bool | None:
    if len(tags) > 5:
        raise HTTPException(
            status_code=400, detail="You can add no more 5 tags to one photo."
        )
    return True


async def assembling_tags(source_tags: list[str], db: AsyncSession) -> List[Tag]:
    tags = []

    for tag_name in source_tags:
        existing_tag = await get_or_create_tag(tag_name, db)
        tags.append(existing_tag)

    return tags


async def create_photo(
    photofile: File(),
    description: str | None,
    user: User,
    db: AsyncSession,
    list_tags: List[str],
):
    """
    The create_photo function save data of a new photo in cloud storage.

    :param body: ContactSchema: Validate the request body
    :param db: AsyncSession: Pass the database session to the function
    :param user: User: Get the user id from the token
    :return: A contact object
    :doc-author: Trelent
    """
    cloudinary.config(
        cloud_name=config.CLOUDINARY_NAME,
        api_key=config.CLOUDINARY_API_KEY,
        api_secret=config.CLOUDINARY_API_SECRET,
        secure=True,
    )

    unique_photo_id = uuid.uuid4()
    public_photo_id = f"Photos_of_user/{user.username}/{unique_photo_id}"
    r = cloudinary.uploader.upload(
        photofile.file, public_id=public_photo_id, overwrite=True
    )

    src_url = r["url"]

    check_tags_quantity(list_tags)
    tags = await assembling_tags(list_tags, db)

    new_photo = Photo(
        path=src_url,
        description=description,
        path_transform=None,
        user_id=user.id,
        tags=tags,
    )

    try:
        db.add(new_photo)
        await db.commit()
        await db.refresh(new_photo)
    except Exception as e:
        await db.rollback()
        raise e
    return {"success message": PHOTO_SUCCESSFULLY_ADDED}


async def edit_photo_description(
    user: User, photo_id: int, description: str, list_tags: List[str], db: AsyncSession
) -> dict:

    query_result = await db.execute(
        select(Photo).where(Photo.user_id == user.id).where(Photo.id == photo_id)
    )
    photo = query_result.scalar()

    check_tags_quantity(list_tags)
    # tags = await assembling_tags(list_tags, db)
    tags = []

    for tag_name in list_tags:
        existing_tag = await get_or_create_tag(tag_name, db)
        tags.append(existing_tag)

    if photo:
        photo.description = description
        # photo.tags = tags
        try:
            await db.commit()
            await db.refresh(photo)
            return photo
        except Exception as e:
            await db.rollback()
            raise e
