use anchor_lang::prelude::*;
use anchor_spl::{
    associated_token::AssociatedToken,
    token::{self, Mint, Token, TokenAccount, Transfer},
};

use crate::errors::EscrowError;
use crate::state::{Config, EscrowAccount, EscrowStatus, CONFIG_SEED, ESCROW_SEED};

#[derive(Accounts)]
#[instruction(task_id: u64)]
pub struct InitializeEscrow<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    /// CHECK: only stored as the release destination owner; no data is read.
    pub agent_wallet: UncheckedAccount<'info>,
    #[account(seeds = [CONFIG_SEED], bump = config.bump)]
    pub config: Account<'info, Config>,
    pub mint: Account<'info, Mint>,
    #[account(
        init,
        payer = payer,
        space = 8 + EscrowAccount::INIT_SPACE,
        seeds = [ESCROW_SEED, task_id.to_le_bytes().as_ref()],
        bump
    )]
    pub escrow: Account<'info, EscrowAccount>,
    /// Vault holding the escrowed tokens, owned by the escrow PDA.
    #[account(
        init,
        payer = payer,
        associated_token::mint = mint,
        associated_token::authority = escrow,
    )]
    pub escrow_vault: Account<'info, TokenAccount>,
    #[account(
        mut,
        token::mint = mint,
        token::authority = payer,
    )]
    pub payer_token_account: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub system_program: Program<'info, System>,
}

pub fn handle_initialize_escrow(
    ctx: Context<InitializeEscrow>,
    task_id: u64,
    amount: u64,
) -> Result<()> {
    require!(amount > 0, EscrowError::ZeroAmount);

    let escrow = &mut ctx.accounts.escrow;
    escrow.task_id = task_id;
    escrow.payer = ctx.accounts.payer.key();
    escrow.agent_wallet = ctx.accounts.agent_wallet.key();
    escrow.treasury = ctx.accounts.config.treasury;
    escrow.mint = ctx.accounts.mint.key();
    escrow.amount = amount;
    escrow.status = EscrowStatus::Funded;
    escrow.authority = ctx.accounts.config.authority;
    escrow.bump = ctx.bumps.escrow;

    token::transfer(
        CpiContext::new(
            ctx.accounts.token_program.key(),
            Transfer {
                from: ctx.accounts.payer_token_account.to_account_info(),
                to: ctx.accounts.escrow_vault.to_account_info(),
                authority: ctx.accounts.payer.to_account_info(),
            },
        ),
        amount,
    )?;

    Ok(())
}
