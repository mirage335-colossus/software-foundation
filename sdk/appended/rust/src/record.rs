//! Bounded canonical field records. Field IDs are strictly increasing and nonzero.

use crate::{abi::*, CodecError, read_u16, read_u32, read_u64, write_u16, write_u32};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Field<'a> {
    pub id: u16,
    pub field_type: u8,
    pub must_understand: bool,
    pub value: &'a [u8],
}

impl<'a> Field<'a> {
    pub const fn new(id: u16, field_type: u8, must_understand: bool, value: &'a [u8]) -> Self {
        Self { id, field_type, must_understand, value }
    }
    pub fn u32(self) -> Result<u32, CodecError> {
        if self.field_type as u32 != FIELD_U32 || self.value.len() != 4 {
            return Err(CodecError::InvalidValue);
        }
        Ok(read_u32(self.value, 0))
    }
    pub fn u64(self) -> Result<u64, CodecError> {
        if self.field_type as u32 != FIELD_U64 || self.value.len() != 8 {
            return Err(CodecError::InvalidValue);
        }
        Ok(read_u64(self.value, 0))
    }
    pub fn boolean(self) -> Result<bool, CodecError> {
        if self.field_type as u32 != FIELD_BOOL || self.value.len() != 1 || self.value[0] > 1 {
            return Err(CodecError::InvalidValue);
        }
        Ok(self.value[0] == 1)
    }
    pub fn utf8(self) -> Result<&'a str, CodecError> {
        if self.field_type as u32 != FIELD_UTF8 { return Err(CodecError::InvalidValue); }
        core::str::from_utf8(self.value).map_err(|_| CodecError::InvalidValue)
    }
    pub fn bytes(self) -> Result<&'a [u8], CodecError> {
        if self.field_type as u32 != FIELD_BYTES { return Err(CodecError::InvalidValue); }
        Ok(self.value)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Record<'a> { bytes: &'a [u8] }

impl<'a> Record<'a> {
    pub fn decode(bytes: &'a [u8]) -> Result<Self, CodecError> {
        validate_record(bytes, 1)?;
        Ok(Self { bytes })
    }
    pub fn fields(self) -> Fields<'a> { Fields { bytes: self.bytes, cursor: 0 } }
}

pub struct Fields<'a> { bytes: &'a [u8], cursor: usize }

impl<'a> Iterator for Fields<'a> {
    type Item = Field<'a>;
    fn next(&mut self) -> Option<Self::Item> {
        if self.cursor == self.bytes.len() { return None; }
        let at = self.cursor;
        let length = read_u32(self.bytes, at + 4) as usize;
        self.cursor += 8 + length;
        Some(Field {
            id: read_u16(self.bytes, at), field_type: self.bytes[at + 2],
            must_understand: self.bytes[at + 3] != 0,
            value: &self.bytes[at + 8..self.cursor],
        })
    }
}

/// Encodes one complete record. On failure, `output` remains unchanged.
pub fn encode(fields: &[Field<'_>], output: &mut [u8]) -> Result<usize, CodecError> {
    if fields.len() > 64 { return Err(CodecError::LimitExceeded); }
    let mut previous = 0;
    let mut total = 0usize;
    for field in fields {
        if field.id <= previous { return Err(CodecError::InvalidValue); }
        previous = field.id;
        validate_value(field.field_type, field.must_understand, field.value, 1)?;
        if field.value.len() > MAX_MESSAGE_BYTES as usize - 8
            || total > MAX_MESSAGE_BYTES as usize - 8 - field.value.len() {
            return Err(CodecError::LimitExceeded);
        }
        total += 8 + field.value.len();
    }
    if total > output.len() { return Err(CodecError::Truncated); }
    let mut cursor = 0;
    for field in fields {
        write_u16(output, cursor, field.id);
        output[cursor + 2] = field.field_type;
        output[cursor + 3] = u8::from(field.must_understand);
        write_u32(output, cursor + 4, field.value.len() as u32);
        output[cursor + 8..cursor + 8 + field.value.len()].copy_from_slice(field.value);
        cursor += 8 + field.value.len();
    }
    Ok(total)
}

fn validate_record(bytes: &[u8], depth: u32) -> Result<(), CodecError> {
    if bytes.len() > MAX_MESSAGE_BYTES as usize || depth > 8 {
        return Err(CodecError::LimitExceeded);
    }
    let mut cursor = 0;
    let mut count = 0;
    let mut previous = 0;
    while cursor < bytes.len() {
        if bytes.len() - cursor < 8 { return Err(CodecError::Truncated); }
        let id = read_u16(bytes, cursor);
        let field_type = bytes[cursor + 2];
        let flags = bytes[cursor + 3];
        let length = read_u32(bytes, cursor + 4) as usize;
        if id <= previous || flags > FIELD_MUST_UNDERSTAND as u8 {
            return Err(CodecError::InvalidValue);
        }
        count += 1;
        if count > 64 { return Err(CodecError::LimitExceeded); }
        cursor += 8;
        if length > bytes.len() - cursor { return Err(CodecError::Truncated); }
        validate_value(field_type, flags != 0, &bytes[cursor..cursor + length], depth)?;
        previous = id;
        cursor += length;
    }
    Ok(())
}

fn validate_value(field_type: u8, required: bool, value: &[u8], depth: u32) -> Result<(), CodecError> {
    let invalid = || Err(CodecError::InvalidValue);
    match field_type as u32 {
        FIELD_U32 => if value.len() != 4 { return invalid(); },
        FIELD_U64 | FIELD_I64 => if value.len() != 8 { return invalid(); },
        FIELD_F64 => {
            if value.len() != 8 { return invalid(); }
            let bits = read_u64(value, 0);
            if bits & 0x7ff0000000000000 == 0x7ff0000000000000
                && bits & 0x000fffffffffffff != 0 && bits != 0x7ff8000000000000 {
                return invalid();
            }
        },
        FIELD_BOOL => if value.len() != 1 || value[0] > 1 { return invalid(); },
        FIELD_UTF8 => if core::str::from_utf8(value).is_err() { return invalid(); },
        FIELD_BYTES => {},
        FIELD_RECORD => validate_record(value, depth + 1)?,
        FIELD_RECORD_LIST => {
            if value.len() < 4 { return Err(CodecError::Truncated); }
            let count = read_u32(value, 0);
            if count > 1024 { return Err(CodecError::LimitExceeded); }
            let mut cursor = 4;
            for _ in 0..count {
                if value.len() - cursor < 4 { return Err(CodecError::Truncated); }
                let length = read_u32(value, cursor) as usize;
                cursor += 4;
                if length > value.len() - cursor { return Err(CodecError::Truncated); }
                validate_record(&value[cursor..cursor + length], depth + 1)?;
                cursor += length;
            }
            if cursor != value.len() { return invalid(); }
        },
        _ => if required { return Err(CodecError::UnknownRequiredField); },
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn golden_record_and_unknown_optional_field() {
        let bytes = [1, 0, 1, 1, 4, 0, 0, 0, 0x78, 0x56, 0x34, 0x12,
            2, 0, 200, 0, 1, 0, 0, 0, 0xaa];
        let record = Record::decode(&bytes).unwrap();
        let mut fields = record.fields();
        assert_eq!(fields.next().unwrap().u32(), Ok(0x12345678));
        assert_eq!(fields.next().unwrap().value, &[0xaa]);
        assert_eq!(fields.next(), None);
        let mut required = bytes;
        required[15] = 1;
        assert_eq!(Record::decode(&required), Err(CodecError::UnknownRequiredField));
    }

    #[test]
    fn rejects_duplicate_ids_and_noncanonical_nan_without_output_change() {
        let number = 1u32.to_le_bytes();
        let mut output = [0xa5; 24];
        let duplicate = [Field::new(1, FIELD_U32 as u8, true, &number); 2];
        assert_eq!(encode(&duplicate, &mut output), Err(CodecError::InvalidValue));
        assert_eq!(output, [0xa5; 24]);
        let nan = 0x7ff0000000000001u64.to_le_bytes();
        assert_eq!(encode(&[Field::new(1, FIELD_F64 as u8, true, &nan)], &mut output),
            Err(CodecError::InvalidValue));
    }

    #[test]
    fn rejects_invalid_utf8_and_incomplete_list() {
        let mut output = [0; 32];
        assert_eq!(encode(&[Field::new(1, FIELD_UTF8 as u8, true, &[0xc0, 0x80])], &mut output),
            Err(CodecError::InvalidValue));
        let list = [1, 0, 0, 0, 4, 0, 0, 0];
        assert_eq!(encode(&[Field::new(1, FIELD_RECORD_LIST as u8, true, &list)], &mut output),
            Err(CodecError::Truncated));
    }
}
