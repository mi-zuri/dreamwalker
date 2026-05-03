function fmt(value: unknown): string {
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

export function logAI(label: string, input: unknown, output: unknown): void {
  console.log(`\n─── AI [${label}] ───`);
  console.log(`IN:  ${fmt(input)}`);
  console.log(`OUT: ${fmt(output)}\n`);
}
