import { request } from './client'

/** 参考别名清洗试算相关接口：只读试算、区域/站点映射与回源补录。 */

export type TrialCategory = {
  数据类别: string
  更正条数: number
  涉及标准编码: string[]
}

export type AliasOverride = {
  id: number
  更正编号: string
  数据类别: string
  标准编码: string
  标准名称: string
  更正别名: string
  别名解释: string
  试算范围: string
  更新时间: string
}

export type AddressRecord = {
  id: number
  地址编号: string
  区域: string
  原始地址: string
  当前旧码: string
  回源状态: string
}

export type TrialDiff = {
  地址编号: string
  区域: string
  原始地址: string
  回源状态: string
  参考类别: string
  旧码: string
  旧码名称: string
  新码: string
  新码名称: string
  命中别名: string
  别名来源: string
  正式清洗旧码: string
  差异类型: string
  是否受影响: boolean
}

export type RegionSummary = {
  区域: string
  参考类别: string
  地址记录数: number
  已回源数: number
  待回源数: number
  差异记录数: number
  影响状态: string
  涉及旧码: string[]
  涉及新码: string[]
}

export type SiteMapping = {
  参考类别: string
  旧码: string
  旧码名称: string
  新码: string
  新码名称: string
  覆盖区域: string[]
  记录数: number
}

export type TrialPreview = {
  试算类别: string
  试算时间: string
  只读说明: string
  汇总: {
    地址记录总数: number
    已回源记录数: number
    待回源记录数: number
    存在差异记录数: number
    受影响区域数: number
    待回源区域数: number
  }
  区域汇总: RegionSummary[]
  站点映射: SiteMapping[]
  差异明细: TrialDiff[]
  全量记录评估: TrialDiff[]
}

async function getJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) throw new Error(`接口返回 ${response.status}，试算数据读取失败`)
  return (await response.json()) as T
}

export async function fetchTrialCategories(): Promise<TrialCategory[]> {
  const payload = await getJson<{ items: TrialCategory[] }>('/api/field_cleanse/trial/categories')
  return payload.items
}

export async function fetchAliasOverrides(category: string): Promise<AliasOverride[]> {
  const query = new URLSearchParams({ category })
  const payload = await getJson<{ items: AliasOverride[] }>(
    `/api/field_cleanse/trial/alias-overrides?${query.toString()}`,
  )
  return payload.items
}

export async function fetchAddressRecords(region?: string): Promise<AddressRecord[]> {
  const query = new URLSearchParams()
  if (region) query.set('region', region)
  const payload = await getJson<{ items: AddressRecord[] }>(
    `/api/field_cleanse/trial/address-records?${query.toString()}`,
  )
  return payload.items
}

export async function fetchTrialPreview(category: string): Promise<TrialPreview> {
  const query = new URLSearchParams({ category })
  return getJson<TrialPreview>(`/api/field_cleanse/trial/preview?${query.toString()}`)
}

export async function fetchEffectiveSnapshot(category: string): Promise<{
  参考类别: string
  生效参考数据: { 标准编码: string; 标准名称: string; 别名列表: string; 数据版本: string }[]
  正式清洗旧码: { 地址编号: string; 当前旧码: string }[]
}> {
  const query = new URLSearchParams({ category })
  return getJson(`/api/field_cleanse/trial/effective-snapshot?${query.toString()}`)
}

export async function registerAddressSource(values: {
  地址编号?: string
  区域: string
  原始地址: string
}): Promise<{ ok: boolean; message: string }> {
  const response = await request('/api/field_cleanse/trial/address-records', {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return await response.json()
}
