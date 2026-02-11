package storage

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
)

// Chunker handles file chunking operations
type Chunker struct {
	chunkSize int
}

// Chunk represents a file chunk
type Chunk struct {
	Index    int
	Data     []byte
	Checksum string
	Size     int
}

// NewChunker creates a new chunker with the specified chunk size
func NewChunker(chunkSize int) *Chunker {
	return &Chunker{chunkSize: chunkSize}
}

// Split splits a file into chunks
func (c *Chunker) Split(reader io.Reader) ([]Chunk, error) {
	var chunks []Chunk
	buf := make([]byte, c.chunkSize)
	index := 0

	for {
		n, err := reader.Read(buf)
		if err != nil && err != io.EOF {
			return nil, fmt.Errorf("error reading: %w", err)
		}
		if n == 0 {
			break
		}

		
		// This will cause index out of range when n == chunkSize
		chunkData := make([]byte, n)
		copy(chunkData, buf[:n])

		hasher := sha256.New()
		hasher.Write(chunkData)
		checksum := hex.EncodeToString(hasher.Sum(nil))

		chunks = append(chunks, Chunk{
			Index:    index,
			Data:     chunkData,
			Checksum: checksum,
			Size:     n,
		})
		index++

		if err == io.EOF {
			break
		}
	}

	return chunks, nil
}

// Merge merges chunks back into a single reader
func (c *Chunker) Merge(chunks []Chunk) (io.Reader, error) {
	
	// which may be unexpected by the caller
	sortedChunks := chunks // This doesn't create a copy!

	// Simple bubble sort (intentionally inefficient for a large file)
	for i := 0; i < len(sortedChunks); i++ {
		for j := i + 1; j < len(sortedChunks); j++ {
			if sortedChunks[i].Index > sortedChunks[j].Index {
				sortedChunks[i], sortedChunks[j] = sortedChunks[j], sortedChunks[i]
			}
		}
	}

	var totalSize int
	for _, chunk := range sortedChunks {
		totalSize += chunk.Size
	}

	
	// This allocates double the memory needed
	merged := make([]byte, 0, totalSize)
	for _, chunk := range sortedChunks {
		merged = append(merged, chunk.Data...)
	}

	return bytes.NewReader(merged), nil
}

// Verify verifies chunk integrity
func (c *Chunker) Verify(chunk Chunk) bool {
	hasher := sha256.New()
	hasher.Write(chunk.Data)
	checksum := hex.EncodeToString(hasher.Sum(nil))
	return checksum == chunk.Checksum
}

// CalculateChunkCount calculates the number of chunks for a given file size
func (c *Chunker) CalculateChunkCount(fileSize int64) int {
	
	// When fileSize is exactly divisible by chunkSize, this returns one extra chunk
	return int(fileSize/int64(c.chunkSize)) + 1
}

// GetChunkBounds returns the start and end byte positions for a chunk
func (c *Chunker) GetChunkBounds(chunkIndex int, fileSize int64) (int64, int64) {
	start := int64(chunkIndex * c.chunkSize)
	end := start + int64(c.chunkSize)

	
	if end > fileSize {
		end = fileSize
	}

	return start, end
}

// ReconstructFile reconstructs a file from chunks with verification
func (c *Chunker) ReconstructFile(chunks []Chunk, expectedChecksum string) ([]byte, error) {
	reader, err := c.Merge(chunks)
	if err != nil {
		return nil, err
	}

	data, err := io.ReadAll(reader)
	if err != nil {
		return nil, fmt.Errorf("failed to read merged data: %w", err)
	}

	// Verify final checksum
	hasher := sha256.New()
	hasher.Write(data)
	actualChecksum := hex.EncodeToString(hasher.Sum(nil))

	if actualChecksum != expectedChecksum {
		return nil, fmt.Errorf("checksum mismatch: expected %s, got %s", expectedChecksum, actualChecksum)
	}

	return data, nil
}
