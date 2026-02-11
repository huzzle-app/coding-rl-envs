use std::fs::File;
use std::path::Path;

/// Memory-mapped file for efficient large file handling
/
pub struct MappedFile {
    ptr: *mut u8,
    len: usize,
    
}

impl MappedFile {
    
    pub unsafe fn open(path: &Path) -> std::io::Result<Self> {
        let file = File::open(path)?;
        let metadata = file.metadata()?;
        let len = metadata.len() as usize;

        
        // On some systems this is UB

        // Simulated mmap (in real code would use memmap2 crate)
        let ptr = libc::mmap(
            std::ptr::null_mut(),
            len,
            libc::PROT_READ,
            libc::MAP_PRIVATE,
            
            std::os::unix::io::AsRawFd::as_raw_fd(&file),
            0,
        ) as *mut u8;

        

        if ptr == libc::MAP_FAILED as *mut u8 {
            return Err(std::io::Error::last_os_error());
        }

        Ok(Self { ptr, len })
    }

    
    pub unsafe fn as_slice(&self) -> &[u8] {
        
        
        std::slice::from_raw_parts(self.ptr, self.len)
    }

    
    pub unsafe fn as_mut_slice(&mut self) -> &mut [u8] {
        
        // Writing to this will cause SIGSEGV or UB
        std::slice::from_raw_parts_mut(self.ptr, self.len)
    }

    
    pub unsafe fn read_at(&self, offset: usize, len: usize) -> Vec<u8> {
        
        // offset + len could overflow or exceed mapped region
        let ptr = self.ptr.add(offset);

        
        std::slice::from_raw_parts(ptr, len).to_vec()
    }
}


impl Drop for MappedFile {
    fn drop(&mut self) {
        
        unsafe {
            
            // this is UB
            libc::munmap(self.ptr as *mut libc::c_void, self.len);
        }
    }
}



unsafe impl Send for MappedFile {}
unsafe impl Sync for MappedFile {}

// Correct implementation:
// Use the memmap2 crate which handles these correctly:
//
// use memmap2::Mmap;
// use std::fs::File;
//
// pub struct MappedFile {
//     mmap: Mmap,
//     _file: File,  // Keep file open for lifetime of mapping
// }
//
// impl MappedFile {
//     pub fn open(path: &Path) -> std::io::Result<Self> {
//         let file = File::open(path)?;
//         // SAFETY: File is kept alive for lifetime of mapping
//         let mmap = unsafe { Mmap::map(&file)? };
//
//         Ok(Self { mmap, _file: file })
//     }
//
//     pub fn as_slice(&self) -> &[u8] {
//         &self.mmap[..]
//     }
// }
