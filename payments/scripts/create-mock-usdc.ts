/**
 * Creates a mock USDC mint (6 decimals, matching real USDC) and mints a test
 * supply to a few test wallets. Real USDC does not exist on devnet, so tests
 * and devnet deployments use this mint instead.
 *
 * Usage:
 *   npx ts-node scripts/create-mock-usdc.ts [recipientPubkey ...]
 *
 * Env:
 *   SOLANA_RPC_URL     RPC endpoint (default http://localhost:8899)
 *   PAYER_KEYPAIR_PATH Keypair that pays fees and acts as mint authority
 *                      (default ~/.config/solana/id.json)
 *
 * If no recipient pubkeys are passed, three throwaway test wallets are
 * generated and their keypairs written to scripts/test-wallets/.
 */
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  Connection,
  Keypair,
  LAMPORTS_PER_SOL,
  PublicKey,
} from "@solana/web3.js";
import {
  createMint,
  getOrCreateAssociatedTokenAccount,
  mintTo,
} from "@solana/spl-token";

const USDC_DECIMALS = 6;
// 1,000 mock USDC per wallet, in base units.
const TEST_SUPPLY_PER_WALLET = 1_000n * 10n ** BigInt(USDC_DECIMALS);

function loadKeypair(filePath: string): Keypair {
  const raw = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  return Keypair.fromSecretKey(Uint8Array.from(raw));
}

async function main() {
  const rpcUrl = process.env.SOLANA_RPC_URL ?? "http://localhost:8899";
  const payerPath =
    process.env.PAYER_KEYPAIR_PATH ??
    path.join(os.homedir(), ".config", "solana", "id.json");

  const connection = new Connection(rpcUrl, "confirmed");
  const payer = loadKeypair(payerPath);
  console.log(`RPC:   ${rpcUrl}`);
  console.log(`Payer: ${payer.publicKey.toBase58()}`);

  // On a local validator the payer may start with zero balance.
  const balance = await connection.getBalance(payer.publicKey);
  if (balance < LAMPORTS_PER_SOL) {
    console.log("Airdropping 10 SOL to payer...");
    const sig = await connection.requestAirdrop(
      payer.publicKey,
      10 * LAMPORTS_PER_SOL
    );
    await connection.confirmTransaction(sig, "confirmed");
  }

  const mint = await createMint(
    connection,
    payer,
    payer.publicKey, // mint authority
    null, // no freeze authority
    USDC_DECIMALS
  );
  console.log(`\nMock USDC mint: ${mint.toBase58()}`);

  // Recipients: CLI args, or generated throwaway wallets.
  let recipients: PublicKey[];
  if (process.argv.length > 2) {
    recipients = process.argv.slice(2).map((a) => new PublicKey(a));
  } else {
    const walletDir = path.join(__dirname, "test-wallets");
    fs.mkdirSync(walletDir, { recursive: true });
    recipients = [];
    for (let i = 0; i < 3; i++) {
      const kp = Keypair.generate();
      fs.writeFileSync(
        path.join(walletDir, `test-wallet-${i}.json`),
        JSON.stringify(Array.from(kp.secretKey))
      );
      recipients.push(kp.publicKey);
    }
    console.log(`Generated 3 test wallets in ${walletDir}`);
  }

  for (const recipient of recipients) {
    const ata = await getOrCreateAssociatedTokenAccount(
      connection,
      payer,
      mint,
      recipient
    );
    await mintTo(
      connection,
      payer,
      mint,
      ata.address,
      payer,
      TEST_SUPPLY_PER_WALLET
    );
    console.log(
      `Minted ${TEST_SUPPLY_PER_WALLET} base units (${
        TEST_SUPPLY_PER_WALLET / 10n ** BigInt(USDC_DECIMALS)
      } mock USDC) to ${recipient.toBase58()}`
    );
  }

  console.log(`\nDone. Set MOCK_USDC_MINT=${mint.toBase58()} in your .env`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
