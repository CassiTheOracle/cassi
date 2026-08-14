#!/usr/bin/env node

import { main } from './cassicore.js'
import { runMain } from './runtime/output.js'

void runMain(() => main())
