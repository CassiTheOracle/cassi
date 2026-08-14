/**
 * Intelligence Layer
 * 
 * Background intelligence processing exports
 */

export { IntelligenceLayer, createIntelligenceLayer } from './IntelligenceLayer.js';
export type {
  IntelligenceLayerOptions,
  DialecticSystem,
  ThinkerModule,
  SubconsciousModule
} from './IntelligenceLayer.js';

export {
  BackgroundProcessor,
  createSafeBackgroundProcessor
} from './BackgroundProcessor.js';
export type {
  IntelligenceProcessor,
  BackgroundProcessorOptions,
  OnCompleteCallback
} from './BackgroundProcessor.js';
