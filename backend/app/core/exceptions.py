from fastapi import HTTPException, status

class SubjectException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str = "Subject operation failed"
    ):
        super().__init__(status_code=status_code, detail=detail)

class DuplicateSubjectException(SubjectException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subject with this name already exists"
        )

class SubjectNotFoundError(SubjectException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found"
        )
