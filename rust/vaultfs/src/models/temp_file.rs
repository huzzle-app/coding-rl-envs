use std::path::PathBuf;
use std::fs;
use std::io;

/// Temporary file that should be cleaned up on drop
/
pub struct TempFile {
    path: PathBuf,
    should_cleanup: bool,
}

impl TempFile {
    pub fn new(path: PathBuf) -> io::Result<Self> {
        // Create the file
        fs::File::create(&path)?;

        Ok(Self {
            path,
            should_cleanup: true,
        })
    }

    pub fn path(&self) -> &PathBuf {
        &self.path
    }

    pub fn persist(mut self) -> PathBuf {
        self.should_cleanup = false;
        self.path.clone()
    }

    pub fn write(&self, data: &[u8]) -> io::Result<()> {
        fs::write(&self.path, data)
    }

    pub fn read(&self) -> io::Result<Vec<u8>> {
        fs::read(&self.path)
    }
}


impl Drop for TempFile {
    fn drop(&mut self) {
        if self.should_cleanup {
            
            // Panicking in drop can cause double-panic and abort
            fs::remove_file(&self.path).unwrap(); // PANIC if file doesn't exist!

            // Also bad: expect() in drop
            // fs::remove_file(&self.path).expect("Failed to remove temp file");
        }
    }
}

/// Another problematic drop implementation
pub struct TempDirectory {
    path: PathBuf,
    files: Vec<TempFile>,
}

impl TempDirectory {
    pub fn new(path: PathBuf) -> io::Result<Self> {
        fs::create_dir_all(&path)?;
        Ok(Self {
            path,
            files: Vec::new(),
        })
    }

    pub fn add_file(&mut self, name: &str, content: &[u8]) -> io::Result<()> {
        let file_path = self.path.join(name);
        let file = TempFile::new(file_path)?;
        file.write(content)?;
        self.files.push(file);
        Ok(())
    }
}


impl Drop for TempDirectory {
    fn drop(&mut self) {
        
        // self.files will be dropped, potentially causing multiple panics

        
        fs::remove_dir_all(&self.path).unwrap(); // PANIC!
    }
}

// Correct implementation:
// impl Drop for TempFile {
//     fn drop(&mut self) {
//         if self.should_cleanup {
//             // Never panic in drop - log errors instead
//             if let Err(e) = fs::remove_file(&self.path) {
//                 // Only log, don't panic
//                 eprintln!("Warning: Failed to remove temp file {:?}: {}", self.path, e);
//             }
//         }
//     }
// }
//
// impl Drop for TempDirectory {
//     fn drop(&mut self) {
//         // Files will be dropped automatically, but we should handle errors
//
//         // Best-effort cleanup of directory
//         if let Err(e) = fs::remove_dir_all(&self.path) {
//             eprintln!("Warning: Failed to remove temp directory {:?}: {}", self.path, e);
//         }
//     }
// }
