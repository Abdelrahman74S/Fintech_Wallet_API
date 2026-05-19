from datetime import datetime, timezone
from sqlmodel import Field, SQLModel
from sqlalchemy import func 

class TimestampMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=lambda: datetime.now().replace(tzinfo=None),
        sa_column_kwargs={
            "server_default": func.now() 
        },
        nullable=False
    )
    
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now().replace(tzinfo=None),
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now()        
        },
        nullable=False
    )