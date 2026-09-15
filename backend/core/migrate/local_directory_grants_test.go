package migrate

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"
)

func TestLocalDirectoryGrantMigrationRoundTrip(t *testing.T) {
	for _, driver := range []string{"sqlite", "postgres"} {
		t.Run(driver, func(t *testing.T) {
			var db *sql.DB
			if driver == "sqlite" {
				db = openRawSQLite(t, filepath.Join(t.TempDir(), "grants.db"))
			} else {
				dsn := os.Getenv(migrationPostgresDSNEnv)
				if dsn == "" {
					t.Skip("disposable PostgreSQL is not configured")
				}
				db = createTemporaryPostgresDatabase(t, dsn, "directory_grants")
			}
			if _, err := db.Exec("CREATE TABLE existing_data (id INTEGER PRIMARY KEY, value TEXT NOT NULL); INSERT INTO existing_data VALUES (1, 'preserved')"); err != nil {
				t.Fatal(err)
			}
			base := filepath.Join("..", "migrations", "dev_mode", "v0_3", "20260914122114_create_local_directory_grants")
			execMigrationFileForDriver(t, db, base+".up.sql", driver)
			if _, err := db.Exec(`INSERT INTO local_directory_grants (id,user_id,path,file_extensions,created_at) VALUES ('grant','owner','/docs','["txt"]',CURRENT_TIMESTAMP)`); err != nil {
				t.Fatal(err)
			}
			execMigrationFileForDriver(t, db, base+".down.sql", driver)
			var value string
			if err := db.QueryRow("SELECT value FROM existing_data WHERE id=1").Scan(&value); err != nil || value != "preserved" {
				t.Fatalf("existing data changed: %s %v", value, err)
			}
			// A complete rollback removes the table and its index, so up can run again.
			execMigrationFileForDriver(t, db, base+".up.sql", driver)
			var count int
			if err := db.QueryRow("SELECT COUNT(*) FROM local_directory_grants").Scan(&count); err != nil || count != 0 {
				t.Fatalf("round trip: %d %v", count, err)
			}
		})
	}
}
