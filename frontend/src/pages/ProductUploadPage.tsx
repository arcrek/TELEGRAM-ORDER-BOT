/**
 * Product Upload page.
 * Premium Dark SaaS Design System.
 */
import { useState, useEffect } from 'react'
import { Card } from '../components/Card'
import { Button } from '../components/Button'
import {
  Upload,
  FileText,
  Clipboard,
  CheckCircle,
  XCircle,
  AlertCircle,
  File,
  List,
  Key,
  FileSpreadsheet,
  RefreshCw,
  Package,
  Layers,
} from 'lucide-react'
import axios from 'axios'
import './ProductUploadPage.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface ParsedItem {
  [key: string]: any
}

interface UploadResult {
  success: number
  failed: number
  errors: Array<{
    index: number
    error: string
    data: any
  }>
}

interface Variation {
  id: string
  name: string
  product_id: string
}

interface ProductGroup {
  product_id: string
  product_name: string
  variations: Variation[]
}

export function ProductUploadPage() {
  const [activeTab, setActiveTab] = useState<'file' | 'paste'>('file')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [pasteContent, setPasteContent] = useState('')
  const [formatType, setFormatType] = useState<'line_separated' | 'key_value' | 'csv'>('line_separated')
  const [parsedData, setParsedData] = useState<ParsedItem[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [previewMode, setPreviewMode] = useState(false)
  
  // Product and variation selection
  const [selectedProductId, setSelectedProductId] = useState<string>('')
  const [selectedVariationId, setSelectedVariationId] = useState<string>('')
  const [productGroups, setProductGroups] = useState<ProductGroup[]>([])
  const [loadingProducts, setLoadingProducts] = useState(false)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.name.endsWith('.txt')) {
        setError('Only .txt files are supported')
        return
      }
      setSelectedFile(file)
      setError(null)
    }
  }

  const handleParseFile = async () => {
    if (!selectedFile) return

    try {
      setUploading(true)
      setError(null)
      
      const formData = new FormData()
      formData.append('file', selectedFile)
      if (formatType) {
        formData.append('format_type', formatType)
      }

      const token = localStorage.getItem('token')
      const response = await axios.post(
        `${API_BASE_URL}/api/products/upload/file`,
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'multipart/form-data',
          },
        }
      )

      setParsedData(response.data.parsed_data || [])
      setPreviewMode(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to parse file')
    } finally {
      setUploading(false)
    }
  }

  const handleParsePaste = async () => {
    if (!pasteContent.trim()) return

    try {
      setUploading(true)
      setError(null)

      const token = localStorage.getItem('token')
      const response = await axios.post(
        `${API_BASE_URL}/api/products/upload/parse`,
        {
          content: pasteContent,
          format_type: formatType,
        },
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      )

      setParsedData(response.data.parsed_data || [])
      setPreviewMode(true)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to parse content')
    } finally {
      setUploading(false)
    }
  }

  // Fetch products and variations
  useEffect(() => {
    fetchProductGroups()
  }, [])

  const fetchProductGroups = async () => {
    try {
      setLoadingProducts(true)
      const token = localStorage.getItem('token')
      const response = await axios.get(
        `${API_BASE_URL}/api/variations`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      setProductGroups(response.data.items || [])
    } catch (err: any) {
      console.error('Failed to load products:', err)
      setError('Failed to load products and variations')
    } finally {
      setLoadingProducts(false)
    }
  }

  const getAvailableVariations = () => {
    if (!selectedProductId) return []
    const productGroup = productGroups.find(p => p.product_id === selectedProductId)
    return productGroup?.variations || []
  }

  const handleProductChange = (productId: string) => {
    setSelectedProductId(productId)
    setSelectedVariationId('') // Reset variation when product changes
  }

  const handleUpload = async () => {
    if (!selectedProductId || !selectedVariationId) {
      setError('Please select both product and variation')
      return
    }

    if (parsedData.length === 0) {
      setError('No data to upload. Please parse file or content first.')
      return
    }

    try {
      setUploading(true)
      setError(null)
      setUploadResult(null)

      // Convert parsed data to upload format
      // Each parsed item needs to be converted to a string for product_data
      const uploadItems = parsedData.map((item) => {
        // Convert item to string (JSON if object, otherwise string)
        let productData: string
        if (typeof item === 'object') {
          // If it's a single key-value object like {data: "value"}, use the value
          const keys = Object.keys(item)
          if (keys.length === 1 && keys[0] === 'data') {
            productData = String(item.data)
          } else {
            productData = JSON.stringify(item)
          }
        } else {
          productData = String(item)
        }

        return {
          product_id: selectedProductId,
          variation_id: selectedVariationId,
          product_data: productData,
        }
      })

      const token = localStorage.getItem('token')
      const response = await axios.post(
        `${API_BASE_URL}/api/products/upload`,
        { products: uploadItems },
        {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      )

      setUploadResult(response.data)
      setPreviewMode(false) // Close preview after upload
      
      // Reset form
      setSelectedFile(null)
      setPasteContent('')
      setParsedData([])
      setSelectedProductId('')
      setSelectedVariationId('')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload products')
    } finally {
      setUploading(false)
    }
  }

  const formatIcons = {
    line_separated: List,
    key_value: Key,
    csv: FileSpreadsheet,
  }

  return (
    <div className="product-upload-page">
      <div className="upload-header">
        <h1>Product Upload</h1>
        <p>Upload products via file or paste content</p>
      </div>

      {/* Tabs */}
      <Card className="upload-tabs-card">
        <div className="upload-tabs">
          <button
            className={`upload-tab ${activeTab === 'file' ? 'active' : ''}`}
            onClick={() => setActiveTab('file')}
          >
            <File size={18} />
            File Upload
          </button>
          <button
            className={`upload-tab ${activeTab === 'paste' ? 'active' : ''}`}
            onClick={() => setActiveTab('paste')}
          >
            <Clipboard size={18} />
            Paste Content
          </button>
        </div>
      </Card>

      {/* Product and Variation Selection */}
      <Card className="upload-content-card">
        <div className="upload-section">
          <div className="upload-section-header">
            <Package size={20} />
            <h2>Select Product & Variation</h2>
          </div>
          
          <div className="selection-fields">
            <div className="selection-field">
              <label htmlFor="product-select">
                <Package size={16} />
                Product
              </label>
              <select
                id="product-select"
                value={selectedProductId}
                onChange={(e) => handleProductChange(e.target.value)}
                className="selection-select"
                disabled={loadingProducts}
              >
                <option value="">Select a product...</option>
                {productGroups.map((group) => (
                  <option key={group.product_id} value={group.product_id}>
                    {group.product_name}
                  </option>
                ))}
              </select>
            </div>

            <div className="selection-field">
              <label htmlFor="variation-select">
                <Layers size={16} />
                Variation
              </label>
              <select
                id="variation-select"
                value={selectedVariationId}
                onChange={(e) => setSelectedVariationId(e.target.value)}
                className="selection-select"
                disabled={!selectedProductId || loadingProducts}
              >
                <option value="">Select a variation...</option>
                {getAvailableVariations().map((variation) => (
                  <option key={variation.id} value={variation.id}>
                    {variation.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* File Upload Tab */}
      {activeTab === 'file' && (
        <Card className="upload-content-card">
          <div className="upload-section">
            <div className="upload-section-header">
              <FileText size={20} />
              <h2>Upload Text File</h2>
            </div>
            
            <div className="file-upload-area">
              <input
                type="file"
                id="file-input"
                accept=".txt"
                onChange={handleFileSelect}
                className="file-input"
              />
              <label htmlFor="file-input" className="file-input-label">
                <Upload size={24} />
                {selectedFile ? selectedFile.name : 'Choose file or drag here'}
              </label>
            </div>

            {selectedFile && (
              <div className="format-selector">
                <label>Format Type:</label>
                <div className="format-buttons">
                  {(['line_separated', 'key_value', 'csv'] as const).map((format) => {
                    const Icon = formatIcons[format]
                    return (
                      <button
                        key={format}
                        className={`format-btn ${formatType === format ? 'active' : ''}`}
                        onClick={() => setFormatType(format)}
                      >
                        <Icon size={16} />
                        {format.replace('_', ' ')}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {error && (
              <div className="error-banner">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            <div className="upload-actions">
              <Button
                onClick={handleParseFile}
                disabled={!selectedFile || uploading}
                variant="primary"
              >
                {uploading ? (
                  <>
                    <RefreshCw size={16} className="spinning" />
                    Parsing...
                  </>
                ) : (
                  <>
                    <FileText size={16} />
                    Parse File
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Paste Content Tab */}
      {activeTab === 'paste' && (
        <Card className="upload-content-card">
          <div className="upload-section">
            <div className="upload-section-header">
              <Clipboard size={20} />
              <h2>Paste Content</h2>
            </div>

            <div className="format-selector">
              <label>Format Type:</label>
              <div className="format-buttons">
                {(['line_separated', 'key_value', 'csv'] as const).map((format) => {
                  const Icon = formatIcons[format]
                  return (
                    <button
                      key={format}
                      className={`format-btn ${formatType === format ? 'active' : ''}`}
                      onClick={() => setFormatType(format)}
                    >
                      <Icon size={16} />
                      {format.replace('_', ' ')}
                    </button>
                  )
                })}
              </div>
            </div>

            <textarea
              className="paste-textarea"
              placeholder="Paste your product data here..."
              value={pasteContent}
              onChange={(e) => setPasteContent(e.target.value)}
              rows={10}
            />

            {error && (
              <div className="error-banner">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            <div className="upload-actions">
              <Button
                onClick={handleParsePaste}
                disabled={!pasteContent.trim() || uploading}
                variant="primary"
              >
                {uploading ? (
                  <>
                    <RefreshCw size={16} className="spinning" />
                    Parsing...
                  </>
                ) : (
                  <>
                    <Clipboard size={16} />
                    Parse Content
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Preview */}
      {previewMode && parsedData.length > 0 && (
        <Card className="preview-card">
          <div className="preview-header">
            <div>
              <h2>Preview ({parsedData.length} items)</h2>
              {selectedProductId && selectedVariationId && (
                <p className="preview-subtitle">
                  Product: {productGroups.find(p => p.product_id === selectedProductId)?.product_name || 'Unknown'} | 
                  Variation: {getAvailableVariations().find(v => v.id === selectedVariationId)?.name || 'Unknown'}
                </p>
              )}
            </div>
            <Button
              onClick={() => setPreviewMode(false)}
              variant="secondary"
              size="small"
            >
              Close Preview
            </Button>
          </div>
          
          <div className="preview-content">
            <div className="preview-table">
              <table>
                <thead>
                  <tr>
                    {Object.keys(parsedData[0] || {}).map((key) => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {parsedData.slice(0, 10).map((item, idx) => (
                    <tr key={idx}>
                      {Object.values(item).map((value: any, valIdx) => (
                        <td key={valIdx}>{String(value)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {parsedData.length > 10 && (
                <p className="preview-note">Showing first 10 of {parsedData.length} items</p>
              )}
            </div>
          </div>

          <div className="preview-actions">
            {selectedProductId && selectedVariationId ? (
              <Button
                onClick={handleUpload}
                disabled={uploading}
                variant="primary"
              >
                {uploading ? (
                  <>
                    <RefreshCw size={16} className="spinning" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload size={16} />
                    Upload {parsedData.length} Items
                  </>
                )}
              </Button>
            ) : (
              <div className="warning-banner">
                <AlertCircle size={16} />
                <span>Please select product and variation before uploading</span>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Upload Result */}
      {uploadResult && (
        <Card className="result-card">
          <div className="result-header">
            <h2>Upload Result</h2>
          </div>
          <div className="result-stats">
            <div className="stat-item success">
              <CheckCircle size={20} />
              <span>Success: {uploadResult.success}</span>
            </div>
            <div className="stat-item failed">
              <XCircle size={20} />
              <span>Failed: {uploadResult.failed}</span>
            </div>
          </div>
          {uploadResult.errors.length > 0 && (
            <div className="error-list">
              <h3>Errors:</h3>
              {uploadResult.errors.map((err, idx) => (
                <div key={idx} className="error-item">
                  <strong>Item {err.index}:</strong> {err.error}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}

