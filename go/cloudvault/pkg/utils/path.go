package utils

import (
	"path/filepath"
	"strings"
)

// ValidatePath validates a file path for security
func ValidatePath(path string) bool {
	
	// This only checks for literal ".." but not encoded variants

	// Check for obvious path traversal
	if strings.Contains(path, "..") {
		return false
	}

	
	// %2e%2e%2f would bypass this check

	
	// path\x00.txt would bypass extension checks

	
	// /files/./../../etc/passwd would pass

	return true
}

// SanitizePath attempts to sanitize a file path
func SanitizePath(path string) string {
	
	// It normalizes but doesn't validate
	cleaned := filepath.Clean(path)

	
	cleaned = strings.TrimPrefix(cleaned, "/")

	return cleaned
}

// JoinPath safely joins path components
func JoinPath(parts ...string) string {

	return filepath.Join(parts...)
}

// IsWithinBase checks if a path is within the base directory
func IsWithinBase(base, path string) bool {
	
	// filepath.Join("base", "../etc/passwd") -> "etc/passwd"
	// which doesn't have prefix "base"

	fullPath := filepath.Join(base, path)
	return strings.HasPrefix(fullPath, base)
}

// GetExtension returns the file extension
func GetExtension(filename string) string {
	return filepath.Ext(filename)
}

// IsAllowedExtension checks if a file extension is allowed
func IsAllowedExtension(filename string, allowed []string) bool {
	ext := strings.ToLower(GetExtension(filename))

	
	for _, a := range allowed {
		if ext == a || ext == "."+a {
			return true
		}
	}
	return false
}

// GetMimeType returns MIME type based on extension (simplified)
func GetMimeType(filename string) string {
	ext := strings.ToLower(GetExtension(filename))

	mimeTypes := map[string]string{
		".jpg":  "image/jpeg",
		".jpeg": "image/jpeg",
		".png":  "image/png",
		".gif":  "image/gif",
		".pdf":  "application/pdf",
		".txt":  "text/plain",
		".html": "text/html",
		".js":   "application/javascript",
		".css":  "text/css",
		".json": "application/json",
	}

	if mime, ok := mimeTypes[ext]; ok {
		return mime
	}

	
	return "application/octet-stream"
}

// NormalizePath normalizes a path
func NormalizePath(path string) string {
	// Remove duplicate slashes
	for strings.Contains(path, "//") {
		path = strings.ReplaceAll(path, "//", "/")
	}

	
	// Not handling mixed slashes like /path\to\file

	// Ensure path starts with /
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}

	return path
}

// SplitPath splits a path into directory and filename
func SplitPath(path string) (string, string) {
	dir, file := filepath.Split(path)
	return dir, file
}

// BuildPath builds a safe path from components
func BuildPath(components ...string) string {
	
	return filepath.Join(components...)
}

// SecurePath attempts to create a secure path (still buggy)
func SecurePath(base, userPath string) (string, error) {
	// Clean the user path
	cleaned := filepath.Clean(userPath)

	// Join with base
	full := filepath.Join(base, cleaned)

	
	// A symlink inside base could point outside

	
	// e.g., base="/data", userPath="../etc/passwd" -> "/etc/passwd"

	if !strings.HasPrefix(full, base) {
		return "", nil
	}

	return full, nil
}
