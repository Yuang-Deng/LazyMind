package datasource

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gorilla/mux"
	"lazymind/core/common/orm"
	"lazymind/core/store"
)

func TestLocalDirectoryGrantLifecycleAndAuthority(t *testing.T) {
	db := orm.MigrateTestDB(t, &orm.LocalDirectoryGrant{})
	store.Init(db.DB, nil, nil)
	t.Cleanup(func() { store.Init(nil, nil, nil) })
	role, sub := "admin", "u1"
	auth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/authservice/auth/validate" || r.Header.Get("Authorization") != "Bearer test" {
			t.Errorf("unexpected auth request: %s", r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"sub": sub, "role": role})
	}))
	defer auth.Close()
	t.Setenv("LAZYMIND_AUTH_SERVICE_URL", auth.URL)
	// Only a grant table exists; creating/listing/revoking cannot require a KB or scan service.
	t.Setenv("LAZYMIND_SCAN_CONTROL_PLANE_URL", "http://127.0.0.1:1")
	dir := t.TempDir()
	body, _ := json.Marshal(LocalDirectoryGrantRequest{Path: dir, FileExtensions: []string{".TXT", "md", "txt"}})
	call := func(handler http.HandlerFunc, method, user, id string) *httptest.ResponseRecorder {
		r := httptest.NewRequest(method, "/", strings.NewReader(string(body)))
		r.Header.Set("Authorization", "Bearer test")
		r.Header.Set("X-User-Id", user)
		r.Header.Set("X-User-Role", "admin")
		r = mux.SetURLVars(r, map[string]string{"grant": id})
		w := httptest.NewRecorder()
		handler(w, r)
		return w
	}
	role = "user"
	if w := call(CreateLocalDirectoryGrant, "POST", "u1", ""); w.Code != 403 {
		t.Fatalf("spoofed admin header accepted: %d %s", w.Code, w.Body)
	}
	role = "admin"
	if w := call(CreateLocalDirectoryGrant, "POST", "u2", ""); w.Code != 403 {
		t.Fatalf("mismatched identity accepted: %d", w.Code)
	}
	w := call(CreateLocalDirectoryGrant, "POST", "u1", "")
	if w.Code != 200 {
		t.Fatalf("create: %d %s", w.Code, w.Body)
	}
	var rows []orm.LocalDirectoryGrant
	if err := db.Find(&rows).Error; err != nil || len(rows) != 1 {
		t.Fatalf("rows=%v err=%v", rows, err)
	}
	first := rows[0]
	if strings.Join(first.FileExtensions, ",") != "md,txt" {
		t.Fatalf("extensions: %v", first.FileExtensions)
	}
	if w := call(ListLocalDirectoryGrants, "GET", "u2", ""); w.Code != 200 || strings.Contains(w.Body.String(), first.ID) {
		t.Fatalf("cross-user list: %s", w.Body)
	}
	sub = "u2"
	if w := call(DeleteLocalDirectoryGrant, "DELETE", "u2", first.ID); w.Code != 200 {
		t.Fatalf("delete: %s", w.Body)
	}
	var count int64
	db.Model(&orm.LocalDirectoryGrant{}).Count(&count)
	if count != 1 {
		t.Fatal("another owner revoked a grant")
	}
	sub = "u1"
	if w := call(DeleteLocalDirectoryGrant, "DELETE", "u1", first.ID); w.Code != 200 {
		t.Fatalf("delete: %s", w.Body)
	}
	db.Model(&orm.LocalDirectoryGrant{}).Count(&count)
	if count != 0 {
		t.Fatal("grant was not revoked")
	}
	if w := call(CreateLocalDirectoryGrant, "POST", "u1", ""); w.Code != 200 {
		t.Fatalf("recreate: %s", w.Body)
	}
	rows = nil
	db.Find(&rows)
	if len(rows) != 1 || rows[0].ID == first.ID {
		t.Fatal("recreated directory reuses withdrawn identity")
	}
}

func TestNormalizeLocalDirectoryGrant(t *testing.T) {
	dir := t.TempDir()
	linked := filepath.Join(t.TempDir(), "link")
	if err := os.Symlink(dir, linked); err != nil {
		t.Fatal(err)
	}
	canonical, _ := filepath.EvalSymlinks(dir)
	if path, _, ok := normalizeLocalDirectoryGrant(LocalDirectoryGrantRequest{Path: linked, FileExtensions: []string{"txt"}}); !ok || path != canonical {
		t.Fatalf("canonical path: %s %v", path, ok)
	}
	file := filepath.Join(dir, "file.txt")
	os.WriteFile(file, []byte("text"), 0600)
	for _, req := range []LocalDirectoryGrantRequest{
		{Path: "relative", FileExtensions: []string{"txt"}},
		{Path: file, FileExtensions: []string{"txt"}},
		{Path: dir, FileExtensions: []string{"*"}},
		{Path: dir, FileExtensions: []string{"../txt"}},
		{Path: dir},
	} {
		if _, _, ok := normalizeLocalDirectoryGrant(req); ok {
			t.Fatalf("accepted invalid grant: %+v", req)
		}
	}
}
