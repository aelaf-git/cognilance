use anchor_lang::prelude::*;

use crate::state::{Config, CONFIG_SEED};

#[derive(Accounts)]
pub struct InitializeProgram<'info> {
    #[account(mut)]
    pub payer: Signer<'info>,
    // `init` guarantees this can only ever succeed once.
    #[account(
        init,
        payer = payer,
        space = 8 + Config::INIT_SPACE,
        seeds = [CONFIG_SEED],
        bump
    )]
    pub config: Account<'info, Config>,
    pub system_program: Program<'info, System>,
}

pub fn handle_initialize_program(
    ctx: Context<InitializeProgram>,
    authority: Pubkey,
    treasury: Pubkey,
) -> Result<()> {
    let config = &mut ctx.accounts.config;
    config.authority = authority;
    config.treasury = treasury;
    config.bump = ctx.bumps.config;
    Ok(())
}
