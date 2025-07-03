import { WalletDoctorClient, WalletDoctorError } from '../src';

describe('WalletDoctorClient', () => {
  describe('constructor', () => {
    it('should create client with valid API key', () => {
      const client = new WalletDoctorClient({
        apiKey: 'wd_12345678901234567890123456789012'
      });
      expect(client).toBeDefined();
    });

    it('should throw error for invalid API key format', () => {
      expect(() => {
        new WalletDoctorClient({
          apiKey: 'invalid_key'
        });
      }).toThrow('API key must start with "wd_" followed by 32 characters');
    });

    it('should use default base URL', () => {
      const client = new WalletDoctorClient({
        apiKey: 'wd_12345678901234567890123456789012'
      });
      // Note: In real implementation, we'd need to expose config or test the actual request
      expect(client).toBeDefined();
    });

    it('should accept custom configuration', () => {
      const client = new WalletDoctorClient({
        apiKey: 'wd_12345678901234567890123456789012',
        baseUrl: 'https://custom.example.com',
        timeout: 60000,
        retryConfig: {
          maxRetries: 5,
          initialDelay: 2000,
          maxDelay: 30000,
          backoffMultiplier: 3
        }
      });
      expect(client).toBeDefined();
    });
  });

  describe('exportTrades', () => {
    let client: WalletDoctorClient;

    beforeEach(() => {
      client = new WalletDoctorClient({
        apiKey: 'wd_12345678901234567890123456789012'
      });
    });

    it('should validate wallet address length', async () => {
      await expect(client.exportTrades('')).rejects.toThrow('Invalid wallet address');
      await expect(client.exportTrades('short')).rejects.toThrow('Invalid wallet address');
      await expect(client.exportTrades('a'.repeat(50))).rejects.toThrow('Invalid wallet address');
    });

    // Note: For real tests, you would mock the fetch calls
    // This is just a structure example
  });

  describe('WalletDoctorError', () => {
    it('should create error with all properties', () => {
      const error = new WalletDoctorError('Test error', 404, 'NOT_FOUND');
      expect(error.message).toBe('Test error');
      expect(error.statusCode).toBe(404);
      expect(error.code).toBe('NOT_FOUND');
      expect(error.name).toBe('WalletDoctorError');
    });

    it('should be instanceof Error', () => {
      const error = new WalletDoctorError('Test', 500);
      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(WalletDoctorError);
    });
  });
}); 