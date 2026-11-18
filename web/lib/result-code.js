import {randomInt} from 'node:crypto';

export const RESULT_CODE_LENGTH = 8;
export const isResultCode = value => typeof value === 'string' && /^[0-9]{8}$/.test(value);

export function resultCode() {
  return String(randomInt(10 ** RESULT_CODE_LENGTH)).padStart(RESULT_CODE_LENGTH,'0');
}
