import type { HttpClient } from "../client/http-client.js";

export interface PlatformDocument {
  id: number;
  documentTitle: string;
  documentDetail?: string | null;
  sortNum: number;
  labels?: string | null;
  createTime: string;
  updateTime: string;
}

interface RawPlatformDocument {
  id: number;
  document_title: string;
  document_detail?: string | null;
  sort_num: number;
  labels?: string | null;
  create_time: string;
  update_time: string;
}

export interface ProductDocument {
  id: number;
  productId: number;
  documentTitle: string;
  documentDetail?: string | null;
  sortNum: number;
  createTime: string;
  updateTime: string;
}

interface RawProductDocument {
  id: number;
  product_id: number;
  document_title: string;
  document_detail?: string | null;
  sort_num: number;
  create_time: string;
  update_time: string;
}

export interface DocumentListParams {
  skip?: number;
  limit?: number;
}

function mapDocument(value: RawPlatformDocument): PlatformDocument {
  return {
    id: value.id,
    documentTitle: value.document_title,
    documentDetail: value.document_detail,
    sortNum: value.sort_num,
    labels: value.labels,
    createTime: value.create_time,
    updateTime: value.update_time,
  };
}

function mapProductDocument(value: RawProductDocument): ProductDocument {
  return {
    id: value.id,
    productId: value.product_id,
    documentTitle: value.document_title,
    documentDetail: value.document_detail,
    sortNum: value.sort_num,
    createTime: value.create_time,
    updateTime: value.update_time,
  };
}

export class FileModule {
  constructor(private readonly http: HttpClient) {}

  async listDocuments(params: DocumentListParams = {}): Promise<PlatformDocument[]> {
    const result = await this.http.request<RawPlatformDocument[]>({
      method: "GET",
      path: "/api/documents",
      query: {
        skip: params.skip ?? 0,
        limit: params.limit ?? 100,
      },
    });
    return result.map(mapDocument);
  }

  async getDocument(documentId: number): Promise<PlatformDocument> {
    const result = await this.http.request<RawPlatformDocument>({
      method: "GET",
      path: `/api/documents/${documentId}`,
    });
    return mapDocument(result);
  }

  async listProductDocuments(productId: number): Promise<ProductDocument[]> {
    const result = await this.http.request<RawProductDocument[]>({
      method: "GET",
      path: `/api/products/${productId}/documents`,
    });
    return result.map(mapProductDocument);
  }
}
