package orm

import "time"

// LocalDirectoryGrant authorizes on-demand reading without a scan source.
// Records are immutable: changing scope requires revoking and creating a new ID.
type LocalDirectoryGrant struct {
	ID             string    `gorm:"column:id;type:varchar(64);primaryKey" json:"id"`
	UserID         string    `gorm:"column:user_id;type:varchar(255);not null;index:idx_local_directory_grants_user" json:"-"`
	Path           string    `gorm:"column:path;type:text;not null" json:"path"`
	FileExtensions []string  `gorm:"column:file_extensions;type:json;serializer:json;not null" json:"file_extensions"`
	CreatedAt      time.Time `gorm:"column:created_at;not null" json:"created_at"`
}

func (LocalDirectoryGrant) TableName() string { return "local_directory_grants" }
