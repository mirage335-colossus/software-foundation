//! Allocation-free builders for the published `foundation.view` v1 records.
//!
//! Values use the canonical appended TLV encoding from `record`; buffers are
//! borrowed from the caller and are never allocated or retained here.

use crate::{abi::*, read_u64, write_u16, write_u32, CodecError};

pub const SERVICE_NAME: &str = "foundation.view";
pub const MAJOR: u32 = 1;
pub const MINOR: u32 = 0;
pub const REPLACE: u32 = 1;
pub const HOST_SERVICE: u32 = 2;

pub const GROUP: u32 = 1;
pub const LABEL: u32 = 2;
pub const BUTTON: u32 = 3;
pub const TOGGLE: u32 = 4;
pub const CHOICE: u32 = 5;
pub const TEXT: u32 = 6;
pub const LIST: u32 = 7;
pub const BITMAP: u32 = 8;
pub const MENU: u32 = 9;

pub const SCHEMA_SHA256_HEX: &str = "7345dda570c5c338f41785c88ebea3f7ba78eff7da07786a0ced43fe4dc411b7";
pub const SCHEMA: [u8; 32] = [
    0x73, 0x45, 0xdd, 0xa5, 0x70, 0xc5, 0xc3, 0x38,
    0xf4, 0x17, 0x85, 0xc8, 0x8e, 0xbe, 0xa3, 0xf7,
    0xba, 0x78, 0xef, 0xf7, 0xda, 0x07, 0x78, 0x6a,
    0x0c, 0xed, 0x43, 0xfe, 0x4d, 0xc4, 0x11, 0xb7,
];

/// A view record builder. A failed append poisons the builder; never submit a
/// builder whose `finish` returned an error. The wire bytes already written
/// remain private to the caller's scratch buffer.
pub struct Builder<'a> {
    output: &'a mut [u8],
    bytes: usize,
    fields: u32,
    previous_id: u16,
    error: Option<CodecError>,
}

impl<'a> Builder<'a> {
    pub fn new(output: &'a mut [u8]) -> Self {
        Self { output, bytes: 0, fields: 0, previous_id: 0, error: None }
    }

    fn fail(&mut self, error: CodecError) {
        if self.error.is_none() { self.error = Some(error); }
    }

    /// Append a typed field after checking its value and canonical ordering.
    pub fn field(&mut self, id: u16, field_type: u8, value: &[u8]) -> &mut Self {
        if self.error.is_some() { return self; }
        if id == 0 || id <= self.previous_id || self.fields >= 64 {
            self.fail(if self.fields >= 64 { CodecError::LimitExceeded } else { CodecError::InvalidValue });
            return self;
        }
        if let Err(error) = validate_value(field_type, value) {
            self.fail(error);
            return self;
        }
        let Some(field_bytes) = value.len().checked_add(8) else {
            self.fail(CodecError::LimitExceeded);
            return self;
        };
        if field_bytes > MAX_MESSAGE_BYTES as usize - self.bytes {
            self.fail(CodecError::LimitExceeded);
            return self;
        }
        if field_bytes > self.output.len().saturating_sub(self.bytes) {
            self.fail(CodecError::Truncated);
            return self;
        }
        let at = self.bytes;
        write_u16(self.output, at, id);
        self.output[at + 2] = field_type;
        self.output[at + 3] = FIELD_MUST_UNDERSTAND as u8;
        write_u32(self.output, at + 4, value.len() as u32);
        self.output[at + 8..at + field_bytes].copy_from_slice(value);
        self.bytes += field_bytes;
        self.fields += 1;
        self.previous_id = id;
        self
    }

    pub fn u32(&mut self, id: u16, value: u32) -> &mut Self {
        self.field(id, FIELD_U32 as u8, &value.to_le_bytes())
    }

    pub fn u64(&mut self, id: u16, value: u64) -> &mut Self {
        self.field(id, FIELD_U64 as u8, &value.to_le_bytes())
    }

    /// Encode a finite IEEE-754 value without narrowing its precision.
    pub fn number(&mut self, id: u16, value: f64) -> &mut Self {
        if !value.is_finite() {
            self.fail(CodecError::InvalidValue);
            return self;
        }
        self.field(id, FIELD_F64 as u8, &value.to_bits().to_le_bytes())
    }

    pub fn boolean(&mut self, id: u16, value: bool) -> &mut Self {
        self.field(id, FIELD_BOOL as u8, &[u8::from(value)])
    }

    pub fn text(&mut self, id: u16, value: &str) -> &mut Self {
        self.field(id, FIELD_UTF8 as u8, value.as_bytes())
    }

    pub fn bytes(&mut self, id: u16, value: &[u8]) -> &mut Self {
        self.field(id, FIELD_BYTES as u8, value)
    }

    pub fn record(&mut self, id: u16, value: &[u8]) -> &mut Self {
        self.field(id, FIELD_RECORD as u8, value)
    }

    pub fn list(&mut self, id: u16, value: &[u8]) -> &mut Self {
        self.field(id, FIELD_RECORD_LIST as u8, value)
    }

    pub fn finish(self) -> Result<usize, CodecError> {
        self.error.map_or(Ok(self.bytes), Err)
    }
}

/// Caller-buffered record-list builder. Every appended record is validated
/// before it is copied into the list.
pub struct ListBuilder<'a> {
    output: &'a mut [u8],
    bytes: usize,
    count: u32,
    error: Option<CodecError>,
}

impl<'a> ListBuilder<'a> {
    pub fn new(output: &'a mut [u8]) -> Self {
        if output.len() < 4 {
            return Self { output, bytes: 0, count: 0, error: Some(CodecError::Truncated) };
        }
        write_u32(output, 0, 0);
        Self { output, bytes: 4, count: 0, error: None }
    }

    pub fn append(&mut self, record: &[u8]) -> &mut Self {
        if self.error.is_some() { return self; }
        if let Err(error) = crate::record::Record::decode(record) {
            self.error = Some(error);
            return self;
        }
        if self.count >= 1024 {
            self.error = Some(CodecError::LimitExceeded);
            return self;
        }
        let Some(entry_bytes) = record.len().checked_add(4) else {
            self.error = Some(CodecError::LimitExceeded);
            return self;
        };
        if entry_bytes > self.output.len().saturating_sub(self.bytes) {
            self.error = Some(CodecError::Truncated);
            return self;
        }
        if entry_bytes > MAX_MESSAGE_BYTES as usize - self.bytes {
            self.error = Some(CodecError::LimitExceeded);
            return self;
        }
        write_u32(self.output, self.bytes, record.len() as u32);
        self.bytes += 4;
        self.output[self.bytes..self.bytes + record.len()].copy_from_slice(record);
        self.bytes += record.len();
        self.count += 1;
        write_u32(self.output, 0, self.count);
        self
    }

    pub fn finish(self) -> Result<usize, CodecError> {
        self.error.map_or(Ok(self.bytes), Err)
    }
}

/// Return an exact `f64` field value, rejecting wrong types, malformed widths,
/// and non-finite values at the typed view boundary.
pub fn field_number(field: crate::record::Field<'_>) -> Result<f64, CodecError> {
    if field.field_type as u32 != FIELD_F64 || field.value.len() != 8 {
        return Err(CodecError::InvalidValue);
    }
    let bits = read_u64(field.value, 0);
    let value = f64::from_bits(bits);
    if value.is_finite() { Ok(value) } else { Err(CodecError::InvalidValue) }
}

/// Build the schema's canonical `rect` record in caller storage.
pub fn rect(output: &mut [u8], x: f64, y: f64, width: f64, height: f64) -> Result<usize, CodecError> {
    let mut builder = Builder::new(output);
    builder.number(1, x).number(2, y).number(3, width).number(4, height);
    builder.finish()
}

/// Build the required identity, generation, kind and bounds fields of a widget.
pub fn widget(output: &mut [u8], id: &str, generation: u64, kind: u32,
              bounds: &[u8]) -> Result<usize, CodecError> {
    if generation == 0 || kind < GROUP || kind > MENU {
        return Err(CodecError::InvalidValue);
    }
    let mut builder = Builder::new(output);
    builder.text(1, id).u64(2, generation).u32(3, kind).record(4, bounds);
    builder.finish()
}

fn validate_value(field_type: u8, value: &[u8]) -> Result<(), CodecError> {
    // View numbers are finite, while the general value codec also admits
    // canonical non-finite values. Retain that typed boundary here.
    if field_type as u32 == FIELD_F64 {
        if value.len() != 8 || !f64::from_bits(read_u64(value, 0)).is_finite() {
            return Err(CodecError::InvalidValue);
        }
    }
    // This field belongs to the outer record at depth one. Reuse the codec's
    // context-aware check so records and list entries begin at depth two.
    crate::record::validate_value(field_type, true, value, 1)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::record::{Field, Record};

    #[test]
    fn rect_and_widget_match_canonical_little_endian_records() {
        let mut rect_bytes = [0; 64];
        let rect_len = rect(&mut rect_bytes, 1.5, -2.0, 3.25, 4.0).unwrap();
        assert_eq!(&rect_bytes[8..16], &1.5f64.to_bits().to_le_bytes());
        assert_eq!(&rect_bytes[16 + 8..16 + 16], &(-2.0f64).to_bits().to_le_bytes());
        let mut widget_bytes = [0; 128];
        let widget_len = widget(&mut widget_bytes, "ok", 7, BUTTON, &rect_bytes[..rect_len]).unwrap();
        let decoded = Record::decode(&widget_bytes[..widget_len]).unwrap();
        let mut fields = decoded.fields();
        assert_eq!(fields.next().unwrap().utf8(), Ok("ok"));
        assert_eq!(fields.next().unwrap().u64(), Ok(7));
        assert_eq!(fields.next().unwrap().u32(), Ok(BUTTON));
        assert_eq!(fields.next().unwrap().id, 4);
        assert_eq!(fields.next(), None);
    }

    #[test]
    fn nested_lists_preserve_borrowed_records_and_invalid_values_poison() {
        let mut item = [0; 16];
        let mut item_builder = Builder::new(&mut item);
        item_builder.text(1, "x");
        let item_len = item_builder.finish().unwrap();
        let mut list = [0; 64];
        let mut list_builder = ListBuilder::new(&mut list);
        list_builder.append(&item[..item_len]);
        let list_len = list_builder.finish().unwrap();
        let mut output = [0; 80];
        let mut builder = Builder::new(&mut output);
        builder.list(1, &list[..list_len]);
        assert!(builder.finish().is_ok());

        let mut invalid = [0; 16];
        let mut bad = Builder::new(&mut invalid);
        bad.number(1, f64::INFINITY);
        assert_eq!(bad.finish(), Err(CodecError::InvalidValue));
    }

    #[test]
    fn typed_number_keeps_full_precision_and_requires_finite_value() {
        let mut output = [0; 16];
        let mut builder = Builder::new(&mut output);
        builder.number(1, 0.10000000000000002);
        let length = builder.finish().unwrap();
        let bytes = &output[..length];
        let field = Record::decode(bytes).unwrap().fields().next().unwrap();
        assert_eq!(field_number(field), Ok(0.10000000000000002));
        let infinity_bytes = f64::INFINITY.to_bits().to_le_bytes();
        let inf = Field::new(1, FIELD_F64 as u8, true, &infinity_bytes);
        assert_eq!(field_number(inf), Err(CodecError::InvalidValue));
    }
    #[test]
    fn nested_record_and_list_fields_preserve_outer_depth_and_first_error() {
        for depth in [7, 8] {
            let mut child = [0u8; 96];
            child[..12].copy_from_slice(&[1, 0, FIELD_U32 as u8, 1, 4, 0, 0, 0, 1, 0, 0, 0]);
            let mut child_len = 12;
            for _ in 1..depth {
                child.copy_within(0..child_len, 8);
                write_u16(&mut child, 0, 1);
                child[2] = FIELD_RECORD as u8;
                child[3] = FIELD_MUST_UNDERSTAND as u8;
                write_u32(&mut child, 4, child_len as u32);
                child_len += 8;
            }
            assert!(Record::decode(&child[..child_len]).is_ok());
            let mut list = [0u8; 104];
            let mut list_builder = ListBuilder::new(&mut list);
            list_builder.append(&child[..child_len]);
            let list_len = list_builder.finish().unwrap();
            for list_field in [false, true] {
                let mut output = [0u8; 128];
                let mut builder = Builder::new(&mut output);
                if list_field { builder.list(1, &list[..list_len]); }
                else { builder.record(1, &child[..child_len]); }
                if depth == 7 {
                    let length = builder.finish().unwrap();
                    assert!(Record::decode(&output[..length]).is_ok());
                } else {
                    builder.number(2, f64::INFINITY);
                    assert_eq!(builder.finish(), Err(CodecError::LimitExceeded));
                }
            }
        }
    }

}
