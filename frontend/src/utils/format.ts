import dayjs from 'dayjs'

const currency = new Intl.NumberFormat('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatMoney(value: string | number): string {
  const numeric = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(numeric)) return '0.00'
  return currency.format(numeric)
}

export function formatYuan(value: string | number): string {
  return `¥${formatMoney(value)}`
}

export function formatDate(value: string): string {
  return dayjs(value).format('YYYY-MM-DD')
}

export function formatDateTime(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export function todayIso(): string {
  return dayjs().format('YYYY-MM-DD')
}

export function monthRange(offset = 0): { from: string; to: string } {
  const base = dayjs().add(offset, 'month')
  return { from: base.startOf('month').format('YYYY-MM-DD'), to: base.endOf('month').format('YYYY-MM-DD') }
}

export function lastNDaysRange(days: number): { from: string; to: string } {
  return {
    from: dayjs().subtract(days - 1, 'day').format('YYYY-MM-DD'),
    to: dayjs().format('YYYY-MM-DD'),
  }
}

export function toNumber(value: string | number): number {
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}
