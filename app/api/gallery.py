from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from beanie import PydanticObjectId

from app.api.deps import CurrentUser, TeacherOrAdmin
from app.models.gallery import Album, Photo, AlbumCreate, AlbumUpdate
from app.models.user import UserRole
from app.services.s3 import upload_album_photo_to_s3, delete_from_s3

router = APIRouter()

def serialize_album(album: Album) -> dict:
    return {
        "id": str(album.id),
        "name": album.name,
        "description": album.description,
        "branch_id": album.branch_id,
        "cover_image_url": album.cover_image_url,
        "photos": [
            {
                "id": p.id,
                "url": p.url,
                "key": p.key,
                "caption": p.caption,
                "created_at": p.created_at.isoformat(),
                "uploaded_by": p.uploaded_by
            } for p in album.photos
        ],
        "created_at": album.created_at.isoformat(),
        "updated_at": album.updated_at.isoformat(),
        "created_by": album.created_by
    }

@router.get("/albums")
async def list_albums(user: CurrentUser, branch_id: Optional[str] = None):
    query = {}
    if branch_id:
        query["$or"] = [{"branch_id": branch_id}, {"branch_id": None}]
    
    # If user is parent, filter by their children's branches
    if user.role == UserRole.PARENT:
        if user.branch_id:
            query["$or"] = [{"branch_id": user.branch_id}, {"branch_id": None}]
        else:
            query["branch_id"] = None

    albums = await Album.find(query).sort("-created_at").to_list()
    return [serialize_album(a) for a in albums]

@router.get("/albums/{album_id}")
async def get_album(album_id: str, user: CurrentUser):
    oid = PydanticObjectId(album_id)
    album = await Album.get(oid)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    return serialize_album(album)

@router.post("/albums", status_code=201)
async def create_album(data: AlbumCreate, user: TeacherOrAdmin):
    album = Album(
        name=data.name,
        description=data.description,
        branch_id=data.branch_id,
        created_by=str(user.id)
    )
    await album.insert()
    return serialize_album(album)

@router.patch("/albums/{album_id}")
async def update_album(album_id: str, data: AlbumUpdate, user: TeacherOrAdmin):
    oid = PydanticObjectId(album_id)
    album = await Album.get(oid)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(album, key, value)
    
    album.updated_at = datetime.utcnow()
    await album.save()
    return serialize_album(album)

@router.delete("/albums/{album_id}", status_code=204)
async def delete_album(album_id: str, user: TeacherOrAdmin):
    oid = PydanticObjectId(album_id)
    album = await Album.get(oid)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    
    # Delete all photos from S3
    for photo in album.photos:
        await delete_from_s3(photo.key)
    
    await album.delete()
    return None

@router.post("/albums/{album_id}/photos")
async def upload_photos(
    album_id: str,
    user: TeacherOrAdmin,
    files: List[UploadFile] = File(...),
):
    oid = PydanticObjectId(album_id)
    album = await Album.get(oid)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    
    for file in files:
        url, key = await upload_album_photo_to_s3(file, album_id=album_id)
        photo = Photo(
            url=url,
            key=key,
            uploaded_by=str(user.id)
        )
        album.photos.append(photo)
        
        # Set first photo as cover if none exists
        if not album.cover_image_url:
            album.cover_image_url = url
            
    album.updated_at = datetime.utcnow()
    await album.save()
    return serialize_album(album)

@router.delete("/albums/{album_id}/photos/{photo_id}")
async def delete_photo(album_id: str, photo_id: str, user: TeacherOrAdmin):
    oid = PydanticObjectId(album_id)
    album = await Album.get(oid)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")
    
    photo_to_delete = next((p for p in album.photos if p.id == photo_id), None)
    if not photo_to_delete:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    await delete_from_s3(photo_to_delete.key)
    album.photos = [p for p in album.photos if p.id != photo_id]
    
    # Update cover if needed
    if album.cover_image_url == photo_to_delete.url:
        album.cover_image_url = album.photos[0].url if album.photos else None
        
    album.updated_at = datetime.utcnow()
    await album.save()
    return serialize_album(album)
