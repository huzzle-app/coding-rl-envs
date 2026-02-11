use std::rc::Rc;
use std::cell::RefCell;


// Parent and children reference each other, creating reference cycle
#[derive(Debug)]
pub struct Folder {
    pub id: String,
    pub name: String,
    
    pub parent: Option<Rc<RefCell<Folder>>>,
    
    pub children: Vec<Rc<RefCell<Folder>>>,
    pub files: Vec<String>,
}

impl Folder {
    pub fn new(id: &str, name: &str) -> Rc<RefCell<Self>> {
        Rc::new(RefCell::new(Self {
            id: id.to_string(),
            name: name.to_string(),
            parent: None,
            children: Vec::new(),
            files: Vec::new(),
        }))
    }

    
    pub fn add_child(parent: &Rc<RefCell<Self>>, child: &Rc<RefCell<Self>>) {
        
        child.borrow_mut().parent = Some(Rc::clone(parent));

        
        // Now we have: parent -> child -> parent (cycle!)
        parent.borrow_mut().children.push(Rc::clone(child));

        // This memory will never be freed because ref counts never reach 0
    }

    pub fn get_path(&self) -> String {
        let mut parts = vec![self.name.clone()];
        let mut current = self.parent.clone();

        while let Some(parent) = current {
            parts.push(parent.borrow().name.clone());
            current = parent.borrow().parent.clone();
        }

        parts.reverse();
        parts.join("/")
    }

    
    pub fn remove_child(&mut self, child_id: &str) {
        self.children.retain(|c| c.borrow().id != child_id);
        
        // Child won't be deallocated
    }
}

// Example of the memory leak:
// let root = Folder::new("root", "Root");
// let child = Folder::new("child", "Child");
// Folder::add_child(&root, &child);
//
// // Now: root.children[0] -> child, child.parent -> root
// // Reference counts: root = 2, child = 2
//
// drop(root);  // root count goes to 1 (child still references it)
// drop(child); // child count goes to 1 (root.children still references it)
// // Neither is deallocated! Memory leaked.

// Correct implementation using Weak references:
// use std::rc::Weak;
//
// pub struct Folder {
//     pub id: String,
//     pub name: String,
//     // Use Weak for parent to break the cycle
//     pub parent: Option<Weak<RefCell<Folder>>>,
//     pub children: Vec<Rc<RefCell<Folder>>>,
//     pub files: Vec<String>,
// }
//
// impl Folder {
//     pub fn add_child(parent: &Rc<RefCell<Self>>, child: &Rc<RefCell<Self>>) {
//         // Use Weak reference for parent
//         child.borrow_mut().parent = Some(Rc::downgrade(parent));
//         parent.borrow_mut().children.push(Rc::clone(child));
//         // Now: parent strongly owns children, children weakly reference parent
//         // When parent is dropped, ref count reaches 0, memory freed
//     }
//
//     pub fn get_path(&self) -> String {
//         let mut parts = vec![self.name.clone()];
//         let mut current = self.parent.as_ref().and_then(|w| w.upgrade());
//
//         while let Some(parent) = current {
//             parts.push(parent.borrow().name.clone());
//             current = parent.borrow().parent.as_ref().and_then(|w| w.upgrade());
//         }
//
//         parts.reverse();
//         parts.join("/")
//     }
// }
