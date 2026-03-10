import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ImageUploader from '@/src/components/Upload/ImageUploader';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock react-dropzone
const mockOnDrop = jest.fn();

jest.mock('react-dropzone', () => ({
  useDropzone: (opts: { onDrop: Function; disabled: boolean }) => {
    mockOnDrop.mockImplementation(opts.onDrop);
    return {
      getRootProps: () => ({
        'data-testid': 'drop-zone',
        role: 'presentation',
        onClick: jest.fn(),
      }),
      getInputProps: () => ({
        'data-testid': 'file-input',
        type: 'file',
        accept: 'image/jpeg,image/png',
        multiple: true,
        onChange: jest.fn(),
      }),
      isDragActive: false,
    };
  },
}));

// Mock useUpload hook
const mockAddFiles = jest.fn().mockReturnValue([]);
const mockRemoveFile = jest.fn();
const mockUploadFiles = jest.fn();
const mockClearFiles = jest.fn();

let mockUseUploadReturn = {
  files: [] as Array<{
    file: File;
    id: string;
    progress: number;
    status: string;
    error?: string;
  }>,
  isUploading: false,
  overallProgress: 0,
  addFiles: mockAddFiles,
  removeFile: mockRemoveFile,
  clearFiles: mockClearFiles,
  uploadFiles: mockUploadFiles,
};

jest.mock('@/src/hooks/useUpload', () => ({
  useUpload: () => mockUseUploadReturn,
}));

// Mock URL.createObjectURL
global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
global.URL.revokeObjectURL = jest.fn();

// Mock exif-extractor
jest.mock('@/src/lib/exif-extractor', () => ({
  extractGPS: jest.fn().mockResolvedValue(null),
  extractMetadata: jest.fn().mockResolvedValue({ gps: null, camera: null, timestamp: null }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createMockFile(name: string, size: number, type: string): File {
  const buffer = new ArrayBuffer(size);
  const blob = new Blob([buffer], { type });
  return new File([blob], name, { type });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ImageUploader', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseUploadReturn = {
      files: [],
      isUploading: false,
      overallProgress: 0,
      addFiles: mockAddFiles,
      removeFile: mockRemoveFile,
      clearFiles: mockClearFiles,
      uploadFiles: mockUploadFiles,
    };
  });

  it('renders the drop zone', () => {
    render(<ImageUploader />);

    expect(screen.getByTestId('drop-zone')).toBeInTheDocument();
    expect(screen.getByTestId('file-input')).toBeInTheDocument();
    expect(
      screen.getByText(/drag & drop street images here/i),
    ).toBeInTheDocument();
  });

  it('shows accepted file type and size info', () => {
    render(<ImageUploader />);

    expect(
      screen.getByText(/jpeg or png, up to 10 mb each, max 10 files/i),
    ).toBeInTheDocument();
  });

  it('handles valid file selection via drop', () => {
    render(<ImageUploader />);

    const validFile = createMockFile('photo.jpg', 1024 * 100, 'image/jpeg');
    mockOnDrop([validFile], []);

    expect(mockAddFiles).toHaveBeenCalledWith([validFile]);
  });

  it('validates file types and shows error for rejected files', () => {
    render(<ImageUploader />);

    const rejected = [
      {
        file: createMockFile('doc.pdf', 1024, 'application/pdf'),
        errors: [{ code: 'file-invalid-type', message: 'File type not accepted' }],
      },
    ];

    mockOnDrop([], rejected);

    expect(mockAddFiles).not.toHaveBeenCalled();
    expect(screen.getByTestId('upload-errors')).toBeInTheDocument();
    expect(screen.getByText(/only jpeg and png allowed/i)).toBeInTheDocument();
  });

  it('validates file size and shows error for oversized files', () => {
    render(<ImageUploader />);

    const rejected = [
      {
        file: createMockFile('huge.jpg', 15 * 1024 * 1024, 'image/jpeg'),
        errors: [{ code: 'file-too-large', message: 'File is too large' }],
      },
    ];

    mockOnDrop([], rejected);

    expect(screen.getByText(/exceeds 10 mb limit/i)).toBeInTheDocument();
  });

  it('shows file previews when files are added', () => {
    const mockFile = createMockFile('street.jpg', 2048, 'image/jpeg');

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      files: [
        {
          file: mockFile,
          id: 'file-1',
          progress: 0,
          status: 'pending',
        },
      ],
    };

    render(<ImageUploader />);

    expect(screen.getByTestId('file-previews')).toBeInTheDocument();
    expect(screen.getByText('street.jpg')).toBeInTheDocument();
  });

  it('shows upload button when files are present', () => {
    const mockFile = createMockFile('photo.png', 4096, 'image/png');

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      files: [
        {
          file: mockFile,
          id: 'file-2',
          progress: 0,
          status: 'pending',
        },
      ],
    };

    render(<ImageUploader />);

    const uploadBtn = screen.getByTestId('upload-button');
    expect(uploadBtn).toBeInTheDocument();
    expect(uploadBtn).toHaveTextContent(/upload 1 file/i);
  });

  it('calls uploadFiles when upload button is clicked', () => {
    const mockFile = createMockFile('photo.jpg', 1024, 'image/jpeg');

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      files: [
        {
          file: mockFile,
          id: 'file-3',
          progress: 0,
          status: 'pending',
        },
      ],
    };

    render(<ImageUploader />);

    fireEvent.click(screen.getByTestId('upload-button'));
    expect(mockUploadFiles).toHaveBeenCalled();
  });

  it('disables upload button while uploading', () => {
    const mockFile = createMockFile('photo.jpg', 1024, 'image/jpeg');

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      isUploading: true,
      overallProgress: 45,
      files: [
        {
          file: mockFile,
          id: 'file-4',
          progress: 45,
          status: 'uploading',
        },
      ],
    };

    render(<ImageUploader />);

    const uploadBtn = screen.getByTestId('upload-button');
    expect(uploadBtn).toBeDisabled();
    expect(uploadBtn).toHaveTextContent(/uploading.*45%/i);
  });

  it('shows "All uploads complete" when all files are done', () => {
    const mockFile = createMockFile('photo.jpg', 1024, 'image/jpeg');

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      files: [
        {
          file: mockFile,
          id: 'file-5',
          progress: 100,
          status: 'complete',
        },
      ],
    };

    render(<ImageUploader />);

    expect(screen.getByTestId('upload-button')).toHaveTextContent(
      /all uploads complete/i,
    );
  });

  it('prevents adding more than 10 files', () => {
    // Simulate 8 files already present
    const existingFiles = Array.from({ length: 8 }, (_, i) => ({
      file: createMockFile(`file-${i}.jpg`, 1024, 'image/jpeg'),
      id: `existing-${i}`,
      progress: 100,
      status: 'complete' as const,
    }));

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      files: existingFiles,
    };

    render(<ImageUploader />);

    // Try to add 3 more (total would be 11)
    const newFiles = [
      createMockFile('new1.jpg', 1024, 'image/jpeg'),
      createMockFile('new2.jpg', 1024, 'image/jpeg'),
      createMockFile('new3.jpg', 1024, 'image/jpeg'),
    ];
    mockOnDrop(newFiles, []);

    expect(mockAddFiles).not.toHaveBeenCalled();
    expect(screen.getByText(/maximum 10 files allowed/i)).toBeInTheDocument();
  });

  it('does not show upload button when no files', () => {
    render(<ImageUploader />);

    expect(screen.queryByTestId('upload-button')).not.toBeInTheDocument();
  });

  it('calls removeFile when remove button on preview is clicked', () => {
    const mockFile = createMockFile('photo.jpg', 1024, 'image/jpeg');

    mockUseUploadReturn = {
      ...mockUseUploadReturn,
      files: [
        {
          file: mockFile,
          id: 'file-rm',
          progress: 0,
          status: 'pending',
        },
      ],
    };

    render(<ImageUploader />);

    fireEvent.click(screen.getByTestId('remove-file-rm'));
    expect(mockRemoveFile).toHaveBeenCalledWith('file-rm');
  });
});
