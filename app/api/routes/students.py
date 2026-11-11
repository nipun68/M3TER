"""
Student Management routes replicating Mongodb/server.js exactly.
Preserves /students CRUD endpoints, schemas, validation, and status codes.
"""
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.dependencies import get_store
from app.models.student import Student
from app.repositories.base import BaseStore
from app.schemas.student import StudentCreateSchema, StudentUpdateSchema, StudentResponseSchema

router = APIRouter(prefix="/students", tags=["Student Management (Existing API)"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=StudentResponseSchema)
def create_student(data: StudentCreateSchema, store: BaseStore = Depends(get_store)):
    student = Student(
        name=data.name,
        age=data.age,
        grade=data.grade,
        city=data.city or "Not Provided",
    )
    saved = store.create_student(student)
    return StudentResponseSchema(
        id=saved.id,
        name=saved.name,
        age=saved.age,
        grade=saved.grade,
        city=saved.city,
        createdAt=saved.created_at.isoformat(),
    )


@router.get("", response_model=List[StudentResponseSchema])
def get_all_students(store: BaseStore = Depends(get_store)):
    students = store.get_all_students()
    return [
        StudentResponseSchema(
            id=s.id,
            name=s.name,
            age=s.age,
            grade=s.grade,
            city=s.city,
            createdAt=s.created_at.isoformat(),
        )
        for s in students
    ]


@router.get("/{student_id}", response_model=StudentResponseSchema)
def get_student_by_id(student_id: str, store: BaseStore = Depends(get_store)):
    s = store.get_student_by_id(student_id)
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentResponseSchema(
        id=s.id,
        name=s.name,
        age=s.age,
        grade=s.grade,
        city=s.city,
        createdAt=s.created_at.isoformat(),
    )


@router.patch("/{student_id}", response_model=StudentResponseSchema)
def update_student(student_id: str, data: StudentUpdateSchema, store: BaseStore = Depends(get_store)):
    updates = data.model_dump(exclude_unset=True)
    updated = store.update_student(student_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentResponseSchema(
        id=updated.id,
        name=updated.name,
        age=updated.age,
        grade=updated.grade,
        city=updated.city,
        createdAt=updated.created_at.isoformat(),
    )


@router.delete("/{student_id}")
def delete_student(student_id: str, store: BaseStore = Depends(get_store)):
    deleted = store.delete_student(student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}
