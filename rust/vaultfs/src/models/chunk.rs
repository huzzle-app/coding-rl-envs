/
/// Chunk stores a reference back to its own data buffer, preventing moves
pub struct Chunk {
    pub data: Vec<u8>,
    pub hash: String,
    pub index: usize,
    
    // This raw pointer points into self.data, making the struct unmovable
    pub data_ptr: *const u8,
    pub data_len: usize,
}

impl Chunk {
    
    pub fn new(data: Vec<u8>, index: usize) -> Self {
        let hash = format!("{:x}", md5_simple(&data));
        let ptr = data.as_ptr();
        let len = data.len();

        
        // and ptr becomes dangling
        Self {
            data,
            hash,
            index,
            data_ptr: ptr,  
            data_len: len,
        }
    }

    
    pub fn get_data_ref(&self) -> &[u8] {
        
        unsafe { std::slice::from_raw_parts(self.data_ptr, self.data_len) }
    }
}

fn md5_simple(data: &[u8]) -> u64 {
    let mut hash: u64 = 0;
    for &byte in data {
        hash = hash.wrapping_mul(31).wrapping_add(byte as u64);
    }
    hash
}

// Correct implementation:
// pub struct Chunk {
//     pub data: Vec<u8>,
//     pub hash: String,
//     pub index: usize,
//     // NO self-referential pointer
// }
//
// impl Chunk {
//     pub fn new(data: Vec<u8>, index: usize) -> Self {
//         let hash = format!("{:x}", md5_simple(&data));
//         Self { data, hash, index }
//     }
//
//     pub fn get_data_ref(&self) -> &[u8] {
//         &self.data  // Safe: borrows from owned data
//     }
// }
