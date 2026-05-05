# Decentralized Learning System Design

## 1. Overview

Decentralized architecture where every USER has equal capabilities. No role-based restrictions on learning activities.

### Core Principle
**Every USER is equal** - same capabilities to learn, create, organize, and be tutored.

## 2. Role System (Simplified)

| Role | Description | Restrictions |
|------|-------------|--------------|
| **USER** | All users (default) | None - has full capabilities |
| **ADMIN** | System administration | System management only |

## 3. USER Capabilities

| Capability | Implementation |
|------------|----------------|
| **Learn** | BKT mastery tracking, FSRS spaced repetition, IRT ability estimation |
| **Get Tutored** | AI Tutor (TutorStateMachine) - all users are served equally |
| **Create Content** | Can create questions, knowledge nodes |
| **Organize** | Can create/manage study groups |
| **Peer Tutor** | AI Agent provides tutoring (not human-to-human) |

## 4. Study Groups (Decentralized Organization)

### StudyGroup Model
```python
class StudyGroup:
    id: int
    name: str
    description: str
    owner_id: int  # Creator, but not "admin" - just group founder
    subject_ids: List[int]  # Related subjects
    tags: List[str]
    is_public: str  # "public" | "private"
    created_at: datetime
```

### StudyGroupMember
```python
class StudyGroupMember:
    group_id: int
    user_id: int
    role: str  # "owner" | "member" | "moderator"
    nickname: str  # Display name in group
    joined_at: datetime
```

### Ownership Model
- Only `owner` can manage group (delete, remove members)
- Any user can create public groups
- Members have equal learning access within group

## 5. Content Contribution

### Community Knowledge
- All USER-created content is shared in community pool
- Questions: approved by ADMIN or auto-approved based on quality
- Knowledge nodes: community-contributed, editable by author

### Contribution Flow
```
USER creates content → Community pool → Used by all users
                              ↓
                        Quality checks (auto)
                              ↓
                        Available for learning
```

## 6. AI Tutor (Centralized Service)

All users receive equal AI tutoring via TutorStateMachine:
- No priority based on role
- BKT mastery tracking per user
- Personalized hints based on misconception detection

## 7. Permission Simplification

### Before (Role-based)
```python
admin_required = Permission([UserRole.ADMIN])
user_required = Permission([UserRole.USER, UserRole.ADMIN])
```

### After (All users equal)
```python
# No role checks for any learning activity
# Only authentication required (get_current_user)
```

## 8. API Endpoints

### Study Groups
- `POST /api/v1/study-groups` - Create group
- `GET /api/v1/study-groups` - List public groups
- `GET /api/v1/study-groups/{id}` - Get group details
- `POST /api/v1/study-groups/{id}/members` - Add member
- `GET /api/v1/study-groups/{id}/members` - List members
- `DELETE /api/v1/study-groups/{id}/members/{user_id}` - Remove member
- `DELETE /api/v1/study-groups/{id}` - Delete group

## 9. File Structure

```
backend/app/
├── models/
│   └── study_group.py          # StudyGroup, StudyGroupMember
├── api/v1/routes/
│   └── study_groups.py         # Study group API
└── core/
    └── permissions.py          # Simplified (no role checks)
```

## 10. Acceptance Criteria

1. **Equal Access**: All authenticated users can use all features
2. **Group Creation**: Any user can create study groups
3. **Content Sharing**: User-created content is shared in community
4. **AI Tutoring**: All users receive equal AI tutoring service
5. **No Role Restrictions**: Learning features work for all users