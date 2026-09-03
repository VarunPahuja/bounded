// Money is integer paise everywhere upstream (contracts/models.py). This is
// the one place it becomes a rupee string for display -- never earlier.
export function paiseToRupees(paise: number): string {
  const rupees = paise / 100;
  return `₹${rupees.toLocaleString("en-IN", { minimumFractionDigits: rupees % 1 === 0 ? 0 : 2 })}`;
}
