package datasource

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"lazymind/core/common"
	"lazymind/core/common/orm"
	"lazymind/core/store"
)

type LocalDirectoryGrantRequest struct {
	Path           string   `json:"path"`
	FileExtensions []string `json:"file_extensions"`
}

type LocalDirectoryGrantsResponse struct {
	Items []orm.LocalDirectoryGrant `json:"items"`
}

var localDirectoryExtension = regexp.MustCompile(`^[a-z0-9][a-z0-9_+-]{0,31}$`)

func normalizeLocalDirectoryGrant(req LocalDirectoryGrantRequest) (string, []string, bool) {
	path := strings.TrimSpace(req.Path)
	if len(path) > 4096 || !filepath.IsAbs(path) {
		return "", nil, false
	}
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return "", nil, false
	}
	info, err := os.Stat(resolved)
	if err != nil || !info.IsDir() {
		return "", nil, false
	}
	if len(req.FileExtensions) == 0 || len(req.FileExtensions) > 200 {
		return "", nil, false
	}
	seen := map[string]bool{}
	extensions := []string{}
	for _, value := range req.FileExtensions {
		ext := strings.TrimPrefix(strings.ToLower(strings.TrimSpace(value)), ".")
		if !localDirectoryExtension.MatchString(ext) {
			return "", nil, false
		}
		if !seen[ext] {
			seen[ext] = true
			extensions = append(extensions, ext)
		}
	}
	sort.Strings(extensions)
	return filepath.Clean(resolved), extensions, true
}

// Validate the current role with auth-service, as local scan source management does.
// Client-supplied role headers must never grant access to the host filesystem.
func canManageLocalDirectoryGrants(r *http.Request) bool {
	authorization := strings.TrimSpace(r.Header.Get("Authorization"))
	if authorization == "" {
		return false
	}
	type identity struct {
		Sub  string `json:"sub"`
		Role string `json:"role"`
	}
	var response struct {
		identity
		Data identity `json:"data"`
	}
	if err := common.ApiPost(r.Context(), common.AuthServiceBaseURL()+"/auth/validate", nil,
		map[string]string{"Authorization": authorization}, &response, 5*time.Second); err != nil {
		return false
	}
	actor := response.identity
	if actor.Sub == "" {
		actor = response.Data
	}
	if actor.Sub != store.UserID(r) {
		return false
	}
	role := strings.ToLower(strings.TrimSpace(actor.Role))
	return role == "admin" || role == "system-admin" || role == "system_admin" || strings.HasSuffix(role, ".admin")
}

func ListLocalDirectoryGrants(w http.ResponseWriter, r *http.Request) {
	userID := strings.TrimSpace(store.UserID(r))
	if userID == "" {
		common.ReplyErr(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	db := store.DB()
	if db == nil {
		common.ReplyErr(w, "store not initialized", http.StatusInternalServerError)
		return
	}
	rows := []orm.LocalDirectoryGrant{}
	if err := db.WithContext(r.Context()).Where("user_id = ?", userID).Order("created_at, id").Find(&rows).Error; err != nil {
		common.ReplyErr(w, "list failed", http.StatusInternalServerError)
		return
	}
	common.ReplyOK(w, LocalDirectoryGrantsResponse{Items: rows})
}

func CreateLocalDirectoryGrant(w http.ResponseWriter, r *http.Request) {
	if !canManageLocalDirectoryGrants(r) {
		common.ReplyErr(w, "forbidden", http.StatusForbidden)
		return
	}
	db := store.DB()
	if db == nil {
		common.ReplyErr(w, "store not initialized", http.StatusInternalServerError)
		return
	}
	var req LocalDirectoryGrantRequest
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 32768)).Decode(&req); err != nil {
		common.ReplyErr(w, "invalid body", http.StatusBadRequest)
		return
	}
	path, extensions, ok := normalizeLocalDirectoryGrant(req)
	if !ok {
		common.ReplyErr(w, "invalid local directory grant", http.StatusBadRequest)
		return
	}
	row := orm.LocalDirectoryGrant{ID: "local-grant:" + uuid.NewString(), UserID: store.UserID(r), Path: path, FileExtensions: extensions, CreatedAt: time.Now().UTC()}
	if err := db.WithContext(r.Context()).Create(&row).Error; err != nil {
		common.ReplyErr(w, "update failed", http.StatusInternalServerError)
		return
	}
	common.ReplyOK(w, row)
}

func DeleteLocalDirectoryGrant(w http.ResponseWriter, r *http.Request) {
	if !canManageLocalDirectoryGrants(r) {
		common.ReplyErr(w, "forbidden", http.StatusForbidden)
		return
	}
	db := store.DB()
	if db == nil {
		common.ReplyErr(w, "store not initialized", http.StatusInternalServerError)
		return
	}
	if err := db.WithContext(r.Context()).Where("id = ? AND user_id = ?", mux.Vars(r)["grant"], store.UserID(r)).Delete(&orm.LocalDirectoryGrant{}).Error; err != nil {
		common.ReplyErr(w, "delete failed", http.StatusInternalServerError)
		return
	}
	common.ReplyOK(w, nil)
}
