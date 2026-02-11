package unit

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/cloudvault/pkg/utils"
)

func TestValidatePath(t *testing.T) {
	t.Run("should reject obvious path traversal", func(t *testing.T) {
		assert.False(t, utils.ValidatePath("../etc/passwd"))
		assert.False(t, utils.ValidatePath("/files/../../../etc/passwd"))
	})

	t.Run("should accept valid paths", func(t *testing.T) {
		assert.True(t, utils.ValidatePath("/files/document.txt"))
		assert.True(t, utils.ValidatePath("/files/folder/image.png"))
	})

	t.Run("should detect URL-encoded traversal", func(t *testing.T) {
		
		assert.False(t, utils.ValidatePath("%2e%2e%2f%2e%2e%2fetc%2fpasswd"),
			"URL-encoded traversal should be detected and rejected")
		assert.False(t, utils.ValidatePath("%2e%2e/etc/passwd"),
			"mixed URL-encoded traversal should be detected")
	})

	t.Run("should detect null byte injection", func(t *testing.T) {
		
		assert.False(t, utils.ValidatePath("/files/evil.php\x00.jpg"),
			"null byte injection should be detected and rejected")
	})

	t.Run("should detect dot-slash sequences", func(t *testing.T) {
		
		assert.False(t, utils.ValidatePath("/files/./../../etc/passwd"),
			"dot-slash traversal sequences should be detected")
	})
}

func TestSanitizePath(t *testing.T) {
	t.Run("should clean basic path", func(t *testing.T) {
		result := utils.SanitizePath("/files/document.txt")
		assert.Equal(t, "files/document.txt", result)
	})

	t.Run("should remove leading slashes", func(t *testing.T) {
		result := utils.SanitizePath("///files/doc.txt")
		assert.Equal(t, "files/doc.txt", result)
	})

	t.Run("should fully prevent traversal", func(t *testing.T) {
		
		result := utils.SanitizePath("../etc/passwd")
		// Sanitized path should not contain traversal sequences
		assert.NotContains(t, result, "..",
			"sanitized path should not contain traversal sequences")
	})
}

func TestJoinPath(t *testing.T) {
	t.Run("should join paths", func(t *testing.T) {
		result := utils.JoinPath("/base", "subdir", "file.txt")
		assert.Equal(t, "/base/subdir/file.txt", result)
	})

	t.Run("should prevent escaping base", func(t *testing.T) {
		
		result := utils.JoinPath("/base", "../etc/passwd")
		// Result should stay within /base, not escape to /etc/passwd
		assert.NotEqual(t, "/etc/passwd", result,
			"JoinPath should prevent escaping base directory")
	})
}

func TestIsWithinBase(t *testing.T) {
	t.Run("should detect path within base", func(t *testing.T) {
		assert.True(t, utils.IsWithinBase("/data", "files/doc.txt"))
	})

	t.Run("should fail to detect escaped path", func(t *testing.T) {
		
		result := utils.IsWithinBase("/data", "../etc/passwd")
		// This should be false but prefix check is flawed
		assert.False(t, result)
	})

	t.Run("should not be fooled by similar prefixes", func(t *testing.T) {
		
		result := utils.IsWithinBase("/data", "../data-backup/secret.txt")
		// After Join: /data-backup/secret.txt
		// Has prefix /data? Yes! But wrong directory
		assert.False(t, result,
			"/data-backup/secret.txt should NOT be considered within /data (prefix confusion)")
	})
}

func TestGetExtension(t *testing.T) {
	t.Run("should get extension", func(t *testing.T) {
		assert.Equal(t, ".txt", utils.GetExtension("document.txt"))
		assert.Equal(t, ".jpg", utils.GetExtension("image.jpg"))
		assert.Equal(t, "", utils.GetExtension("noextension"))
	})

	t.Run("should only get last extension", func(t *testing.T) {
		
		assert.Equal(t, ".jpg", utils.GetExtension("malware.php.jpg"))
	})
}

func TestIsAllowedExtension(t *testing.T) {
	allowed := []string{".jpg", ".png", ".gif", ".pdf"}

	t.Run("should allow valid extensions", func(t *testing.T) {
		assert.True(t, utils.IsAllowedExtension("image.jpg", allowed))
		assert.True(t, utils.IsAllowedExtension("document.pdf", allowed))
	})

	t.Run("should reject invalid extensions", func(t *testing.T) {
		assert.False(t, utils.IsAllowedExtension("script.php", allowed))
		assert.False(t, utils.IsAllowedExtension("program.exe", allowed))
	})

	t.Run("should not be bypassed by double extension", func(t *testing.T) {
		
		// malware.php.jpg passes because .jpg is allowed, but .php should be caught
		assert.False(t, utils.IsAllowedExtension("malware.php.jpg", allowed),
			"double extension attack (malware.php.jpg) should be rejected")
	})
}

func TestGetMimeType(t *testing.T) {
	t.Run("should return correct mime types", func(t *testing.T) {
		assert.Equal(t, "image/jpeg", utils.GetMimeType("photo.jpg"))
		assert.Equal(t, "image/png", utils.GetMimeType("image.png"))
		assert.Equal(t, "application/pdf", utils.GetMimeType("doc.pdf"))
	})

	t.Run("should return safe mime type for unknown", func(t *testing.T) {
		result := utils.GetMimeType("file.xyz")
		assert.NotEmpty(t, result, "unknown extension should still return a MIME type")
		// application/octet-stream is acceptable as long as Content-Disposition is set
	})
}

func TestNormalizePath(t *testing.T) {
	t.Run("should remove duplicate slashes", func(t *testing.T) {
		assert.Equal(t, "/path/to/file", utils.NormalizePath("//path//to//file"))
	})

	t.Run("should add leading slash", func(t *testing.T) {
		assert.Equal(t, "/path/to/file", utils.NormalizePath("path/to/file"))
	})

	t.Run("should handle backslashes", func(t *testing.T) {
		
		result := utils.NormalizePath(`/path\to\file`)
		assert.NotContains(t, result, `\`,
			"backslashes should be converted to forward slashes for cross-platform safety")
	})
}

func TestSecurePath(t *testing.T) {
	t.Run("should create secure path", func(t *testing.T) {
		path, err := utils.SecurePath("/data", "files/doc.txt")
		assert.NoError(t, err)
		assert.Equal(t, "/data/files/doc.txt", path)
	})

	t.Run("should fail to prevent symlink escape", func(t *testing.T) {
		
		// If /data/link -> /etc, then /data/link/passwd would work
		path, _ := utils.SecurePath("/data", "symlink/passwd")
		// This passes the check but symlink could point outside
		assert.NotEmpty(t, path)
	})

	t.Run("should fail to prevent path traversal", func(t *testing.T) {
		
		path, _ := utils.SecurePath("/data", "../etc/passwd")
		// After Join and Clean: /etc/passwd
		// HasPrefix("/etc/passwd", "/data") = false
		assert.Empty(t, path)
	})
}

func TestBuildPath(t *testing.T) {
	t.Run("should build path from components", func(t *testing.T) {
		path := utils.BuildPath("base", "subdir", "file.txt")
		assert.Equal(t, "base/subdir/file.txt", path)
	})

	t.Run("should validate components", func(t *testing.T) {
		
		path := utils.BuildPath("base", "../escape", "file.txt")
		assert.Contains(t, path, "base",
			"BuildPath should not allow components to escape the base directory")
	})
}
