use anchor_lang::prelude::*;

#[error_code]
pub enum EscrowError {
    #[msg("Escrow is not in the required status for this operation")]
    InvalidStatus,
    #[msg("Signer is not the configured program authority")]
    Unauthorized,
    #[msg("Escrow amount must be greater than zero")]
    ZeroAmount,
    #[msg("Arithmetic overflow in amount math")]
    MathOverflow,
}
