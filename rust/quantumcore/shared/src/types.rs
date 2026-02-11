use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use std::marker::PhantomData;


// Covariance/contravariance problem with lifetimes

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Price(pub Decimal);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Quantity(pub u64);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderId(pub String);


pub struct PriceRef<'a> {
    
    // But we might need invariance for soundness
    _marker: PhantomData<&'a Price>,
    price: *const Decimal,
}

impl<'a> PriceRef<'a> {
    
    pub fn new(price: &'a Price) -> Self {
        Self {
            _marker: PhantomData,
            price: &price.0 as *const Decimal,
        }
    }

    
    pub fn get(&self) -> Decimal {
        
        // if the lifetime was extended due to variance
        unsafe { *self.price }
    }
}


pub struct Container<'a, T> {
    data: Vec<T>,
    
    _marker: PhantomData<&'a mut T>,  // This makes it invariant in T
}

impl<'a, T: Clone> Container<'a, T> {
    pub fn new() -> Self {
        Self {
            data: Vec::new(),
            _marker: PhantomData,
        }
    }

    
    pub fn get_ref(&self, index: usize) -> Option<&'a T> {
        
        // The returned reference could outlive the borrow
        self.data.get(index).map(|t| unsafe {
            
            std::mem::transmute::<&T, &'a T>(t)
        })
    }
}

// Type aliases for the trading system
pub type Symbol = String;
pub type AccountId = String;
pub type TradeId = String;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Currency {
    USD,
    EUR,
    GBP,
    JPY,
    BTC,
    ETH,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Money {
    pub amount: Decimal,
    pub currency: Currency,
}

impl Money {
    pub fn new(amount: Decimal, currency: Currency) -> Self {
        Self { amount, currency }
    }

    
    pub fn as_float(&self) -> f64 {
        
        // For financial calculations this is dangerous
        use rust_decimal::prelude::ToPrimitive;
        self.amount.to_f64().unwrap_or(0.0)
    }

    
    pub fn convert_to(&self, target: Currency, rate: f64) -> Money {
        
        
        let new_amount = self.as_float() * rate;

        Money {
            amount: Decimal::from_f64_retain(new_amount).unwrap_or(Decimal::ZERO),
            currency: target,
        }
    }
}

// Correct implementation:
// pub struct PriceRef<'a> {
//     price: &'a Decimal,
// }
//
// impl<'a> PriceRef<'a> {
//     pub fn new(price: &'a Price) -> Self {
//         Self { price: &price.0 }
//     }
//
//     pub fn get(&self) -> Decimal {
//         *self.price
//     }
// }

// Correct Money conversion:
// pub fn convert_to(&self, target: Currency, rate: Decimal) -> Money {
//     let new_amount = self.amount * rate;
//     Money {
//         amount: new_amount,
//         currency: target,
//     }
// }
